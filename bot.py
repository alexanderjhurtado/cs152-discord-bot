# bot.py
import discord
from discord.ext import commands
import os
import json
import logging
import re
import requests
from datetime import datetime
from uuid import uuid4
from report import Report
from manual_review import ManualReview
from message_processor import MessageProcessor
from embed_views import AbuseWarningView, AbuseWarningEmbed, TargetedWarningView, TargetedWarningEmbed, DetectedKeywordsView, DetectedKeywordsEmbed

# Set up logging to the console
logger = logging.getLogger('discord')
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)

# There should be a file called 'tokens.json' inside the same folder as this file
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
        self.reports = {} # Map from case ID to the state of their report
        self.manual_reviews = {} # Map from case ID to a manual review corresponding to their
        self.perspective_key = key
        self.message_processor = MessageProcessor()

    async def on_ready(self):
        print(f'{self.user.name} has connected to Discord! It\'s in these guilds:')
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
            return
            # await self.handle_channel_message(message)
        else:
            await self.handle_dm(message)

    async def on_message_edit(self, message_before, message_after):
        await self.handle_channel_message(message_after)

    async def handle_dm(self, message):
        # Handle a help message
        if message.content == Report.HELP_KEYWORD:
            reply =  "Use the `report` command to begin the reporting process.\n"
            reply += "Use the `cancel` command to cancel the report and manual review process.\n"
            await message.channel.send(reply)
            return
        author_id = message.author.id
        responses = []
        # Only respond to messages if they're part of a reporting flow
        if author_id not in self.reports and not message.content.startswith(Report.START_KEYWORD):
            return
        # If we don't currently have an active report for this user, add one
        if author_id not in self.reports:
            self.reports[author_id] = Report(self, message.author)
        # Let the report class handle this message; forward all the messages it returns to us
        current_report = self.reports[author_id]
        responses = await current_report.handle_message(message)
        for r in responses:
            await message.channel.send(r)
        if current_report.report_complete():
            report_info = current_report.gather_report_information()
            manual_review_case_id = str(author_id) + datetime.now().strftime('%Y%m%d%H%M%S%f') + str(uuid4())
            if author_id in self.reports:
                self.reports.pop(author_id)
            self.manual_reviews[manual_review_case_id] = ManualReview(
                case_id=manual_review_case_id,
                client=self,
                report_info=report_info,
                reporting_channel=message.channel)
            await self.manual_reviews[manual_review_case_id].initial_message()

    async def handle_channel_message(self, message):
        # Only handle messages sent in the "group-#" channel
        if not message.channel.name == f'group-{self.group_num}':
            return
        mod_channel = self.mod_channels[message.guild.id]
        # process the message content
        self.message_processor.process_message(message)
        # identify and warn against abusive users
        abusive_users = self.message_processor.user_abuse_threshold_exceeded()
        if len(abusive_users) > 0:
            for user, messages in abusive_users:
                await mod_channel.send(
                    embed=AbuseWarningEmbed(messages), 
                    view=AbuseWarningView(messages))
        # identity and warn about targeted entities
        targeted_entities = self.message_processor.entity_abuse_threshold_exceeded()
        if len(targeted_entities) > 0:
            for entity, mentions in targeted_entities:
                await mod_channel.send(
                    embed=TargetedWarningEmbed(entity, mentions), 
                    view=TargetedWarningView(
                        mentions, 
                        entity,
                        self.message_processor, 
                        mod_channel.send))

    async def terminate_case(self, author_id, manual_review_case_id, message, channel):
        if message:
            await channel.send(message)
        if author_id in self.reports:
            self.reports.pop(author_id)
        if manual_review_case_id in self.manual_reviews:
            self.manual_reviews.pop(manual_review_case_id)


client = ModBot(perspective_key)
client.run(discord_token)
