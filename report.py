from enum import Enum, auto
import discord
import re

class State(Enum):
    REPORT_START = auto()
    AWAITING_MESSAGE = auto()
    MESSAGE_CONFIRMATION = auto()
    MESSAGE_IDENTIFIED = auto()
    REPORT_COMPLETE = auto()
    IMMINENT_DANGER = auto()
    SELECT_ABUSE = auto()

class Report:
    START_KEYWORD = "report"
    CANCEL_KEYWORD = "cancel"
    HELP_KEYWORD = "help"
    INFO_KEYWORD = "info"
    YES_KEYWORD = "yes"
    NO_KEYWORD = "no"

    ABUSE_TYPES = [
        "Bullying",
        "Hate Speech",
        "Sexual Harrassment",
        "Revealing Personal Information",
        "Advocating Violence",
        "Other"
    ]

    def __init__(self, client):
        self.state = State.REPORT_START
        self.client = client
        self.message = None
        self.abuse_type = None

    def select_abuse_message(self):
        reply = "Please select which abuse type best matches your report (reply with the corresponding number):\n"
        for i, abuse_type in enumerate(self.ABUSE_TYPES):
            reply += f"{i+1}. {abuse_type}\n"
        reply += "\nFor more information about these categories, type `info`."
        return reply

    async def handle_message(self, message):
        '''
        This function makes up the meat of the user-side reporting flow. It defines how we transition between states and what
        prompts to offer at each of those states. You're welcome to change anything you want; this skeleton is just here to
        get you started and give you a model for working with Discord.
        '''

        if message.content == self.CANCEL_KEYWORD:
            self.state = State.REPORT_COMPLETE
            return ["Report cancelled."]

        if self.state == State.REPORT_START:
            reply =  "Thank you for starting the reporting process. "
            reply += "Say `help` at any time for more information.\n\n"
            reply += "Please copy paste the link to the message you want to report.\n"
            reply += "You can obtain this link by right-clicking the message and clicking `Copy Message Link`."
            self.state = State.AWAITING_MESSAGE
            return [reply]

        if self.state == State.AWAITING_MESSAGE:
            # Parse out the three ID strings from the message link
            m = re.search('/(\d+)/(\d+)/(\d+)', message.content)
            if not m:
                return ["I'm sorry, I couldn't read that link. Please try again or say `cancel` to cancel."]
            guild = self.client.get_guild(int(m.group(1)))
            if not guild:
                return ["I cannot accept reports of messages from guilds that I'm not in. Please have the guild owner add me to the guild and try again."]
            channel = guild.get_channel(int(m.group(2)))
            if not channel:
                return ["It seems this channel was deleted or never existed. Please try again or say `cancel` to cancel."]
            try:
                message = await channel.fetch_message(int(m.group(3)))
            except discord.errors.NotFound:
                return ["It seems this message was deleted or never existed. Please try again or say `cancel` to cancel."]

            # Here we've found the message - it's up to you to decide what to do next!
            self.state = State.MESSAGE_CONFIRMATION
            self.message = message
            return [
                "I found this message:", "```" + message.author.name + ": " + message.content + "```", \
                "Is this the content you wish to report? Reply `yes` or `no`."
            ]

        if self.state == State.MESSAGE_CONFIRMATION:
            if message.content == self.YES_KEYWORD:
                self.state = State.MESSAGE_IDENTIFIED
                return ["Thanks for confirming.", \
                        "Are you in imminent danger from this message? Reply `yes` or `no`."]
            if message.content == self.NO_KEYWORD:
                self.state = State.AWAITING_MESSAGE
                self.message = None
                return ["Sorry we weren't able to find that material. Please submit another link to the content you wish to report."]


        if self.state == State.MESSAGE_IDENTIFIED:
            # Checks if the user is in imminent danger
            if message.content == self.YES_KEYWORD:
                self.state = State.IMMINENT_DANGER
                reply = "Please immediately alert the local authorities by dialing 911.\n\n"
                reply += "Would you like us to forward the relevant message information to the authorities? Reply `yes` or `no`."
                return [reply]
            if message.content == self.NO_KEYWORD:
                self.state = State.SELECT_ABUSE
                return [self.select_abuse_message()]

        if self.state == State.IMMINENT_DANGER:
            # Allows the user to send relevant message info to the local authorities
            # Presents the user with potential abuse types to choose from
            if message.content in [self.YES_KEYWORD, self.NO_KEYWORD]:
                self.state = State.SELECT_ABUSE
                imminent_danger_reply = ""
                if message.content == self.YES_KEYWORD:
                    imminent_danger_reply += "All relevant information has been sent to the local authorities. \n"
                    imminent_danger_reply += "In the meantime, please help us assess the reported content.\n\n"
                else:
                    imminent_danger_reply += "Please help us assess the reported content.\n\n"

                select_abuse_reply = self.select_abuse_message()
                return [imminent_danger_reply, select_abuse_reply]

        if self.state == State.SELECT_ABUSE:
            if message.content == self.INFO_KEYWORD:
                return ["Information about Abuse types..."]
            if message.content in [str(i+1) for i in range(len(self.ABUSE_TYPES))]:
                self.abuse_type = self.ABUSE_TYPES[int(message.content) - 1]
                self.state = State.REPORT_COMPLETE
                reply = "Thank you for reporting.\n"
                reply += f"The following content has been flagged for review as `{self.abuse_type}` material:\n"
                reply += f"```{self.message.author.name}: {self.message.content}```\n"
                reply += "Our content moderation team will review this content and assess "
                reply += "next steps, potentially including removing content and contacting "
                reply += "local authorities.\n\n"
                reply += "In the meantime, consider blocking the user to prevent "
                reply += "further exposure to their content."
                return [reply]

        return []

    def report_complete(self):
        return self.state == State.REPORT_COMPLETE
