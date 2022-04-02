## CS 152 Discord Bot

This is a Discord bot created for the `CS 152: Trust and Safety Engineering` course at Stanford University (Fall 2021). 
This particular bot handles two main components: 
 1. the automated detection of targeted harassment campaigns, and 
 2. functionality allowing moderators to effectively manage user reporting and manual review using a button interface.


### Automated abuse detection
This bot implements a user-friendly button UI that allows moderators to automatically detect and kick abusive users, delete their messages, and give them a warning in their direct messages.
Targeted abuse is detected using Google's [Perspective API](https://www.perspectiveapi.com/) and named entity recognition.
The bot also combats word substitutions by automatically detecting keywords associated with targeted abuse campaigns using a variant of [tf-idf](https://en.wikipedia.org/wiki/Tf%E2%80%93idf).

### User reporting and manual review flow
This bot fleshes out a comprehensive abuse reporting and manual review flow via Discord DMs. It can handle batch reporting of messages for targeted harassment campaigns and integration  with Twitter for cross-platform reporting.

### Demo + Credits

Here's a [video demo](https://www.youtube.com/watch?v=TznqDKTS0-g) of the Discord bot in action. 
Credit to the CS 152 staff for providing code that handles connecting to Discord channels.
