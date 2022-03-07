import discord
from discord.ui import View

class AbuseWarningView(View):
    def __init__(self, messages):
        super().__init__()
        self.messages = messages
        self.user = messages[0].author
        self.channel = messages[0].channel

    @discord.ui.button(label='Send warning', style=discord.ButtonStyle.blurple)
    async def send_warning_callback(self, button, interaction):
        await interaction.response.defer()
        button.label = 'Warning sent'
        button.disabled = True
        warning_message = (
            f"This is a warning from the moderators of `{self.channel.name}`.\n"
            f"We've flagged your messages as abusive content.\n"
            "Please refrain from using abusive language in the channel.")
        await self.user.send(embed=AbuseWarningEmbed(self.messages))
        await self.user.send(content=warning_message)
        await interaction.edit_original_message(view=self)

    @discord.ui.button(label='Delete all messages', style=discord.ButtonStyle.gray)
    async def delete_message_callback(self, button, interaction):
        await interaction.response.defer()
        button.label = 'Messages deleted'
        button.disabled = True
        for message in self.messages:
            try:
                await message.delete()
            except discord.errors.NotFound as err:
                pass
        await interaction.edit_original_message(view=self)

    @discord.ui.button(label='Kick user', style=discord.ButtonStyle.red)
    async def kick_user_callback(self, button, interaction):
        await interaction.response.defer()
        button.label = 'User kicked'
        button.disabled = True
        await self.channel.send(f'{self.user.name} has been kicked.') # simulate user being kicked
        await interaction.edit_original_message(view=self)

class AbuseWarningEmbed(discord.Embed):
    def __init__(self, messages):
        title = 'Abusive user detected'
        description = f'<@{messages[0].author.id}> said:'
        time = None
        for message in messages:
            if time != message.created_at.strftime("%b %-m, %Y"):
                time = message.created_at.strftime("%b %-m, %Y")
                description += f'\n{time}\n'
            description += f'"{truncate_string(message.content)}" [[link]({message.jump_url})]\n\n'
        super().__init__(title=title, description=description, color=0xFFA500)


class TargetedWarningView(View):
    def __init__(self, mentions, entity, message_processor, send_to_mod_channel):
        super().__init__()
        self.mentions = mentions
        self.entity = entity
        self.message_processor = message_processor
        self.send_to_mod_channel = send_to_mod_channel
        self.channel = mentions[0]['original_message'].channel
        self.mentions_by_user = {}
        for mention_obj in mentions:
            user = mention_obj['original_message'].author
            message = mention_obj['original_message']
            self.mentions_by_user[user] = self.mentions_by_user.get(user, []) + [message]

    @discord.ui.button(label='See associated keywords', style=discord.ButtonStyle.green)
    async def see_words_callback(self, button, interaction):
        await interaction.response.defer()
        detected_keywords = self.message_processor.compute_tf_idf_by_token(self.mentions)
        button.label = 'No keywords detected'
        button.disabled = True
        if len(detected_keywords) > 0:
            button.label = 'See message below'
            await self.send_to_mod_channel(
                view=DetectedKeywordsView(detected_keywords, self.message_processor), 
                embed=DetectedKeywordsEmbed(detected_keywords, self.entity))
        await interaction.edit_original_message(view=self)

    @discord.ui.button(label='Send warnings', style=discord.ButtonStyle.blurple)
    async def send_warning_callback(self, button, interaction):
        await interaction.response.defer()
        button.label = 'Warnings sent'
        button.disabled = True
        warning_message = (
            f"This is a warning from the moderators of `{self.channel.name}`.\n"
            f"We've flagged your messages as abusive content.\n"
            "Please refrain from using abusive language in the channel.")
        for user, messages in self.mentions_by_user.items():
            await user.send(embed=AbuseWarningEmbed(messages))
            await user.send(content=warning_message)
        await interaction.edit_original_message(view=self)

    @discord.ui.button(label='Delete all messages', style=discord.ButtonStyle.gray)
    async def delete_message_callback(self, button, interaction):
        await interaction.response.defer()
        button.label = 'Messages deleted'
        button.disabled = True
        for _, messages in self.mentions_by_user.items():
            for message in messages:
                try:
                    await message.delete()
                except discord.errors.NotFound as err:
                    pass
        await interaction.edit_original_message(view=self)

    @discord.ui.button(label='Kick users', style=discord.ButtonStyle.red)
    async def kick_user_callback(self, button, interaction):
        await interaction.response.defer()
        button.label = 'Users kicked'
        button.disabled = True
        for user, _ in self.mentions_by_user.items():
            await self.channel.send(f'{user.name} has been kicked.') # simulate user being kicked
        await interaction.edit_original_message(view=self)

class TargetedWarningEmbed(discord.Embed):
    def __init__(self, entity, mentions):
        mentions_by_user = {}
        for mention_obj in mentions:
            user = mention_obj['original_message'].author
            message = mention_obj['original_message']
            mentions_by_user[user] = mentions_by_user.get(user, []) + [message]
        title = 'Targeted harassment detected'
        description = f'Here are abusive messages mentioning the entity: `{entity}`.\n'
        for user, messages in mentions_by_user.items():
            description += f'<@{user.id}> said:\n'
            for message in messages:
                description += f'"{truncate_string(message.content)}" [[link]({message.jump_url})]\n\n'
        super().__init__(title=title, description=description, color=0xED1500)


class DetectedKeywordsView(View):
    def __init__(self, detected_keywords, message_processor):
        super().__init__()
        self.detected_keywords = detected_keywords
        self.message_processor = message_processor

    @discord.ui.button(label='Flag keywords in chat', style=discord.ButtonStyle.red)
    async def callback(self, button, interaction):
        await interaction.response.defer()
        button.label = 'Keywords will be flagged'
        button.disabled = True
        self.message_processor.update_flagged_tokens(self.detected_keywords)
        await interaction.edit_original_message(view=self)

class DetectedKeywordsEmbed(discord.Embed):
    def __init__(self, detected_keywords, entity):
        title = f'Detected keywords'
        description = f'Here are keywords associated with abuse towards `{entity}`:\n'
        for word in detected_keywords:
            description += f'`{word}`\n'
        super().__init__(title=title, description=description)

def truncate_string(string, truncation_length=240):
    '''
    Truncate string to a certain length and add ellipsis if appropriate
    '''
    return string[:truncation_length] + ("..." if len(string) > truncation_length else "")
