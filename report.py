from enum import Enum, auto
import discord
import re

class State(Enum):
    REPORT_START = auto()
    AWAITING_MESSAGE = auto()
    MESSAGE_IDENTIFIED = auto()
    REPORT_COMPLETE = auto()
    IMMINENT_DANGER = auto()
    SELECT_ABUSE = auto()

class Report:
    START_KEYWORD = "report"
    CANCEL_KEYWORD = "cancel"
    HELP_KEYWORD = "help"
    YES_KEYWORD = "yes"
    NO_KEYWORD = "no"

    def __init__(self, client):
        self.state = State.REPORT_START
        self.client = client
        self.message = None

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
            self.state = State.MESSAGE_IDENTIFIED
            return ["I found this message:", "```" + message.author.name + ": " + message.content + "```", \
                    "Are you in imminent danger from this message? Reply `yes` or `no`."]

        if self.state == State.MESSAGE_IDENTIFIED:
            if message.content == self.YES_KEYWORD:
                self.state = State.IMMINENT_DANGER
                reply = "Please immediately alert the local authorities by dialing 911.\n\n"
                reply += "Would you like us to forward the relevant message information to the authorities? Reply `yes` or `no`."
                return [reply]
            if message.content == self.NO_KEYWORD:
                self.state = State.SELECT_ABUSE

        if self.state == State.IMMINENT_DANGER:
            if message.content in [self.YES_KEYWORD, self.NO_KEYWORD]:
                self.state = State.SELECT_ABUSE
                reply = ""
                if message.content == self.YES_KEYWORD:
                    reply += "All relevant information has been sent to the local authorities. \n"
                    reply += "In the meantime, please help us assess the reported content.\n\n"
                else:
                    reply += "Please help us assess the reported content.\n\n"
                print(reply)
                return [reply]

        return []

    def report_complete(self):
        return self.state == State.REPORT_COMPLETE
