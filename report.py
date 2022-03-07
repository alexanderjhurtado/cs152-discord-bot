from enum import Enum, auto
import discord
import re

class State(Enum):
    REPORT_START = auto()
    AWAITING_MESSAGE = auto()
    MESSAGE_CONFIRMATION = auto()
    MESSAGE_IDENTIFIED = auto()
    IMMINENT_DANGER = auto()
    SELECT_ABUSE = auto()
    CHECK_TARGETED_HARRASSMENT = auto()
    ADD_HARRASSMENT_MESSAGES = auto()
    ADD_TWITTER_HANDLE = auto()
    CHECK_BEING_SILENCED = auto()
    REPORT_COMPLETE = auto()

class Report:
    START_KEYWORD = "report"
    CANCEL_KEYWORD = "cancel"
    HELP_KEYWORD = "help"
    INFO_KEYWORD = "info"
    YES_KEYWORD = "yes"
    NO_KEYWORD = "no"
    DONE_KEYWORD = "done"
    SKIP_KEYWORD = "skip"

    ABUSE_DEFINITIONS = {
        "Bullying": "Intent to harm, intimidate, or coerce (someone perceived as vulnerable).",
        "Hate Speech": "Abusive or threatening speech or writing that expresses prejudice against a particular group, especially on the basis of race, religion, or sexual orientation.",
        "Sexual Harrassment": "Content that depicts sexually explicit activities",
        "Revealing Personal Information": "Content that exposes a user's personal, sensitive information without consent",
        "Advocating Violence": "Depiction of especially vivid, brutal and realistic acts of violence",
        "Other": "General category that includes all malicious content that is may be considered in violation of our guidelines",
    }

    ABUSE_TYPES = [
        "Bullying",
        "Hate Speech",
        "Sexual Harrassment",
        "Revealing Personal Information",
        "Advocating Violence",
        "Other"
    ]

    def __init__(self, client, author):
        self.state = State.REPORT_START
        self.client = client
        self.author = author
        self.message = None
        self.report_imminent_danger = False
        self.abuse_type = None
        self.targeted_harrassment = False
        self.targeted_harrassment_messages = set()
        self.target_twitter_handle = None
        self.being_silenced = False

    def report_complete_message(self):
        reply = "Thank you for reporting.\n"
        reply += f"The following content has been flagged for review as `{self.abuse_type}` material:\n"
        reply += f"```{self.message.author.name}: {self.message.content}```\n"
        if self.targeted_harrassment:
            reply += "We have also flagged this message as part of a targeted harrassment campaign.\n"
            if len(self.targeted_harrassment_messages) > 0:
                reply += "The following content will be included as part of the report:\n"
                reply += "```"
                for targeted_message in self.targeted_harrassment_messages:
                    reply += f"{targeted_message.author.name}: {targeted_message.content}\n"
                reply += "```"
            if self.target_twitter_handle:
                reply += f"The Twitter handle `{self.target_twitter_handle}` will be forwarded to the Twitter abuse review team.\n"
            if self.being_silenced:
                reply += "We have flagged that this user is being silenced as part of the targeted harrassment campaign.\n"
            reply += "\n"
        reply += "Our content moderation team will review this content and assess "
        reply += "next steps, potentially including removing content and contacting "
        reply += "local authorities.\n\n"
        reply += "In the meantime, consider blocking the user to prevent "
        reply += "further exposure to their content."
        return reply

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
            elif message.content == self.NO_KEYWORD:
                self.state = State.AWAITING_MESSAGE
                self.message = None
                return ["Sorry we weren't able to find that material. Please submit another link to the content you wish to report."]
            else:
                return ["Sorry, please reply with `yes` or `no`."]


        if self.state == State.MESSAGE_IDENTIFIED:
            # Checks if the user is in imminent danger
            if message.content == self.YES_KEYWORD:
                self.state = State.IMMINENT_DANGER
                reply = "Please immediately alert the local authorities by dialing 911.\n\n"
                reply += "Would you like us to forward the relevant message information to the authorities? Reply `yes` or `no`."
                return [reply]
            elif message.content == self.NO_KEYWORD:
                self.state = State.SELECT_ABUSE
                return [self.select_abuse_message()]
            else:
                return ["Sorry, please reply with `yes` or `no`."]

        if self.state == State.IMMINENT_DANGER:
            # Allows the user to send relevant message info to the local authorities
            # Presents the user with potential abuse types to choose from
            if message.content in [self.YES_KEYWORD, self.NO_KEYWORD]:
                self.state = State.SELECT_ABUSE
                imminent_danger_reply = ""
                if message.content == self.YES_KEYWORD:
                    self.report_imminent_danger = True
                    imminent_danger_reply += "We will process and send the message information to the local authorities.\n"
                    imminent_danger_reply += "In the meantime, please help us assess the reported content.\n\n"
                else:
                    imminent_danger_reply += "Please help us assess the reported content.\n\n"

                select_abuse_reply = self.select_abuse_message()
                return [imminent_danger_reply, select_abuse_reply]
            else:
                return ["Sorry, please reply with `yes` or `no`."]

        if self.state == State.SELECT_ABUSE:
            if message.content == self.INFO_KEYWORD:
                reply = ""
                for abuse in self.ABUSE_DEFINITIONS:
                    reply += f"{abuse}: {self.ABUSE_DEFINITIONS[abuse]}\n\n"
                return [reply]
            if message.content in [str(i+1) for i in range(len(self.ABUSE_TYPES))]:
                self.abuse_type = self.ABUSE_TYPES[int(message.content) - 1]
                self.state = State.CHECK_TARGETED_HARRASSMENT
                reply = "Is this message part of a targeted harrassment campaign?\n"
                reply += "Reply `yes` or `no`. For more information on what qualifies, type `info`"
                # self.state = State.REPORT_COMPLETE
                # reply = "Thank you for reporting.\n"
                # reply += f"The following content has been flagged for review as `{self.abuse_type}` material:\n"
                # reply += f"```{self.message.author.name}: {self.message.content}```\n"
                # reply += "Our content moderation team will review this content and assess "
                # reply += "next steps, potentially including removing content and contacting "
                # reply += "local authorities.\n\n"
                # reply += "In the meantime, consider blocking the user to prevent "
                # reply += "further exposure to their content."
                return [reply]
            else:
                reply = f'Sorry, please reply with a number between 1 and {len(self.ABUSE_TYPES)}'
                reply += self.select_abuse_message()
                return [reply]

        if self.state == State.CHECK_TARGETED_HARRASSMENT:
            if message.content == self.YES_KEYWORD:
                self.targeted_harrassment = True
                self.state = State.ADD_HARRASSMENT_MESSAGES
                reply = "If you wish to report more messages as part of this campaign, please reply "
                reply += "with each message link in separate messages. Once completed,"
                reply += " or if you have no additional messages to report, type `done`."
                return [reply]
            if message.content == self.NO_KEYWORD:
                self.state = State.REPORT_COMPLETE
                return [self.report_complete_message()]
            if message.content == self.INFO_KEYWORD:
                reply = "A targeted harrassment campaign is any series of messages "
                reply += "that qualify as abusive material aimed at a particular person or "
                reply += "entity. These are often performed by multiple individuals, but can "
                reply += "also stem from a single account."
                return [reply]
            else:
                return ["Sorry, please reply with `yes`, `no`, or `info`."]

        if self.state == State.ADD_HARRASSMENT_MESSAGES:
            if message.content == self.DONE_KEYWORD:
                self.state = State.ADD_TWITTER_HANDLE
                reply = ""
                if len(self.targeted_harrassment_messages) > 0:
                    reply += "Thank you for reporting those additional messages.\n"
                reply += "If you would like to add the Twitter handle of the "
                reply += "user being targeted to your report, please type their handle below. "
                reply += "If not, please type `skip`."
                return [reply]
            else:
                m = re.search('/(\d+)/(\d+)/(\d+)', message.content)
                if not m:
                    return ["I'm sorry, I couldn't read that link. Please try again or say `done` to finish adding messages."]
                guild = self.client.get_guild(int(m.group(1)))
                if not guild:
                    return ["I cannot accept reports of messages from guilds that I'm not in. Please have the guild owner add me to the guild and try again."]
                channel = guild.get_channel(int(m.group(2)))
                if not channel:
                    return ["It seems this channel was deleted or never existed. Please try again or say `done` to finish adding messages."]
                try:
                    message = await channel.fetch_message(int(m.group(3)))
                except discord.errors.NotFound:
                    return ["It seems this message was deleted or never existed. Please try again or say `done` to finish adding messages."]
                if self.message != message:
                    self.targeted_harrassment_messages.add(message)
                reply = "The following content was identified and added to the report:\n"
                reply += f"```{message.author.name}: {message.content}```\n"
                reply += "Please reply with another message link or type `done` to finish adding messages."
                return [reply]

        if self.state == State.ADD_TWITTER_HANDLE:
            if message.content == self.SKIP_KEYWORD:
                self.state = State.CHECK_BEING_SILENCED
                reply = "Is this user being silenced by the harrassment campaign? "
                reply += "Does this threaten their open expression? Reply `yes` or `no`."
                return [reply]
            self.target_twitter_handle = message.content
            # Check if twitter handle is valid
            ## Mark invalid and set self.target_twitter_handle to None if not valid.
            ## Save and check being silenced if valid
            self.state = State.CHECK_BEING_SILENCED
            reply = "We have identified the following Twitter account as being targeted:\n"
            reply += f"```Twitter Handle: {self.target_twitter_handle}```\n"
            reply += "Is this user being silenced by the harrassment campaign? "
            reply += "Does this threaten their open expression? Reply `yes` or `no`."
            return [reply]

        if self.state == State.CHECK_BEING_SILENCED:
            if message.content in [self.YES_KEYWORD, self.NO_KEYWORD]:
                if message.content == self.YES_KEYWORD:
                    self.being_silenced = True
                self.state = State.REPORT_COMPLETE
                return [self.report_complete_message()]
            else:
                return ["Sorry, please reply with `yes` or `no`."]


        return []

    def gather_report_information(self):
        return (
            {
                "author": self.author,
                "message": self.message,
                "report_imminent_danger": self.report_imminent_danger,
                "abuse_type": self.abuse_type,
                "targeted_harrassment": self.targeted_harrassment,
                "targeted_harrassment_messages": self.targeted_harrassment_messages,
                "target_twitter_handle": self.target_twitter_handle,
                "being_silenced": self.being_silenced,
            }
        )

    def report_complete(self):
        return self.state == State.REPORT_COMPLETE
