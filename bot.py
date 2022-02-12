# bot.py
import discord
from discord.ext import commands
from discord.ui import View
import os
import json
import logging
import re
import requests
from report import Report
import spacy


TOTAL_SCORE_THRESHOLD = 7.5
INDIVIDUAL_SCORE_THRESHOLD = 0.625

# Set up logging to the console
logger = logging.getLogger('discord')
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)

# There should be a file called 'token.json' inside the same folder as this file
token_path = 'tokens.json'
if not os.path.isfile(token_path):
    raise Exception(f"{token_path} not found!")
with open(token_path) as f:
    # If you get an error here, it means your token is formatted incorrectly. Did you put it in quotes?
    tokens = json.load(f)
    discord_token = tokens['discord']
    perspective_key = tokens['perspective']


class ModBot(discord.Client):
    def __init__(self, key):
        intents = discord.Intents.default()
        super().__init__(command_prefix='.', intents=intents)
        self.group_num = None   
        self.mod_channels = {} # Map from guild to the mod channel id for that guild
        self.reports = {} # Map from user IDs to the state of their report
        self.perspective_key = key
        self.named_entity_model = spacy.load('en_core_web_sm')
        self.entity_scores = {}
        self.entity_mentions = {}

    async def on_ready(self):
        print(f'{self.user.name} has connected to Discord! It is these guilds:')
        for guild in self.guilds:
            print(f' - {guild.name}')
        print('Press Ctrl-C to quit.')
        # Parse the group number out of the bot's name
        match = re.search('[gG]roup (\d+) [bB]ot', self.user.name)
        if match:
            self.group_num = match.group(1)
        else:
            raise Exception("Group number not found in bot's name. Name format should be \"Group # Bot\".")
        # Find the mod channel in each guild that this bot should report to
        for guild in self.guilds:
            for channel in guild.text_channels:
                if channel.name == f'group-{self.group_num}-mod':
                    self.mod_channels[guild.id] = channel

    async def on_message(self, message):
        '''
        This function is called whenever a message is sent in a channel that the bot can see (including DMs). 
        Currently the bot is configured to only handle messages that are sent over DMs or in your group's "group-#" channel. 
        '''
        # Ignore messages from us 
        if message.author.id == self.user.id:
            return
        # Check if this message was sent in a server ("guild") or if it's a DM
        if message.guild:
            await self.handle_channel_message(message)
        else:
            await self.handle_dm(message)

    async def handle_dm(self, message):
        # Handle a help message
        if message.content == Report.HELP_KEYWORD:
            reply =  "Use the `report` command to begin the reporting process.\n"
            reply += "Use the `cancel` command to cancel the report process.\n"
            await message.channel.send(reply)
            return
        author_id = message.author.id
        responses = []
        # Only respond to messages if they're part of a reporting flow
        if author_id not in self.reports and not message.content.startswith(Report.START_KEYWORD):
            return
        # If we don't currently have an active report for this user, add one
        if author_id not in self.reports:
            self.reports[author_id] = Report(self)
        # Let the report class handle this message; forward all the messages it returns to uss
        responses = await self.reports[author_id].handle_message(message)
        for r in responses:
            await message.channel.send(r)
        # If the report is complete or cancelled, remove it from our map
        if self.reports[author_id].report_complete():
            self.reports.pop(author_id)

    async def handle_channel_message(self, message):
        # Only handle messages sent in the "group-#" channel
        if not message.channel.name == f'group-{self.group_num}':
            return 
        # grab mod channel in case we need to forward info there
        mod_channel = self.mod_channels[message.guild.id]
        # extract Perspective score and entity mentions from message
        scores = self.eval_text(message)
        entities = self.eval_entities(message)
        # Forward message to mod channel if it's harassment-like
        if any(score >= INDIVIDUAL_SCORE_THRESHOLD for score in scores.values()):
            embed = discord.Embed(
                title=f'Potentially abusive message detected\n', 
                description=f'<@{message.author.id}> said:\n"{self.truncate_string(message.content)}" [[link]({message.jump_url})]',
                color=0xED1500
            )
            await mod_channel.send(embed=embed, view=AbuseWarningView(message))
            # Identify any targeted entities and forward warning to mod channel
            targeted_entities = self.update_targeted_entities(entities, scores, message)
            if len(targeted_entities) > 0:
                await mod_channel.send("‼️ Possible harassment campaign detected ‼️\nHere's a list of harassment targets: ")
                await mod_channel.send(self.code_format(json.dumps({'targeted_entities': targeted_entities }, indent=2)))

    def eval_text(self, message):
        '''
        Given a message, forwards the message to Perspective and returns a dictionary of scores.
        '''
        PERSPECTIVE_URL = 'https://commentanalyzer.googleapis.com/v1alpha1/comments:analyze'
        url = PERSPECTIVE_URL + '?key=' + self.perspective_key
        data_dict = {
            'comment': {'text': message.content},
            'languages': ['en'],
            'requestedAttributes': {
                                    'SEVERE_TOXICITY': {}, 'IDENTITY_ATTACK': {}, 
                                    'THREAT': {}, 'TOXICITY': {}, 
                                },
            'doNotStore': True
        }
        response = requests.post(url, data=json.dumps(data_dict))
        response_dict = response.json()
        scores = {}
        for attr in response_dict["attributeScores"]:
            scores[attr] = response_dict["attributeScores"][attr]["summaryScore"]["value"]
        return scores

    def eval_entities(self, message):
        '''
        Given a message, evaluate the text for named entities and returns a set of their referred names.
        '''
        named_entities = set()
        entity_doc = self.named_entity_model(message.content)
        for entity in entity_doc.ents:
            if entity.label_ == "PERSON" or entity.label_ == "NORP":
                named_entities.add(entity.text)
        return named_entities

    def update_targeted_entities(self, entity_set, perspective_scores, message):
        '''
        Given a set of entities and the Perspective scores of their originator message, update each entity's
        targeted harassment score and return a list of entities whose harassment score is greater than some threshold
        -- this collection represents the entities who are being targeted with harasssment.
        '''
        for entity in entity_set:
            curr_score = self.entity_scores.get(entity, 0)
            curr_score += self.threshold_get(perspective_scores, 'SEVERE_TOXICITY', INDIVIDUAL_SCORE_THRESHOLD)
            curr_score += self.threshold_get(perspective_scores, 'TOXICITY', INDIVIDUAL_SCORE_THRESHOLD)
            curr_score += self.threshold_get(perspective_scores, 'IDENTITY_ATTACK', INDIVIDUAL_SCORE_THRESHOLD)
            curr_score += self.threshold_get(perspective_scores, 'THREAT', INDIVIDUAL_SCORE_THRESHOLD)
            self.entity_scores[entity] = curr_score
            self.entity_mentions[entity] = self.entity_mentions.get(entity, []) + [
                {'message_id': message.id, 'author': message.author.name, 'content': message.content}
            ]
        return self.identify_targeted_entities(threshold=TOTAL_SCORE_THRESHOLD)

    def identify_targeted_entities(self, threshold):
        '''
        Determines the set of entities whose total harassment score is greater than the given threshold and returns
        those entities as a list. This list represents the set of entities who are being targeted with harassment.
        '''
        targeted_entities = []
        for entity, harassment_score in self.entity_scores.items():
            if harassment_score >= threshold:
                mentions = self.entity_mentions[entity]
                targeted_entities.append({ 
                    'name': entity, 
                    'total_harassment_score': harassment_score,
                    'avg_harassment_score': float(harassment_score / len(mentions)),
                    'mentions': mentions, })
        return targeted_entities
    
    def code_format(self, text):
        return "```" + text + "```"

    def threshold_get(self, dictionary, key, threshold):
        '''
        Grabs the value of the given key from the given dictionary as long as that value is at least the given threshold.
        If the value is not at least the threshold, then this method will return 0.
        '''
        return dictionary[key] if dictionary[key] >= threshold else 0

    def truncate_string(self, string):
        '''
        Truncate string to a certain length and add ellipsis if appropriate
        '''
        TRUNCATION_LENGTH = 325
        return string[:TRUNCATION_LENGTH] + ("..." if len(string) > TRUNCATION_LENGTH else "")

class AbuseWarningView(View):
    def __init__(self, message):
        super().__init__()
        self.message = message

    @discord.ui.button(label='Delete message', style=discord.ButtonStyle.gray)
    async def delete_message_callback(self, button, interaction):
        button.label = 'Message deleted'
        button.disabled = True
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label='Kick user', style=discord.ButtonStyle.red)
    async def kick_user_callback(self, button, interaction):
        button.label = 'User kicked'
        button.disabled = True
        await interaction.response.edit_message(view=self)
            
        
client = ModBot(perspective_key)
client.run(discord_token)