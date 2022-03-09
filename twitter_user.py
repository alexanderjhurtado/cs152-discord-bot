import twint
import nest_asyncio
import os

async def getTwitterUser(username):
    nest_asyncio.apply()

    c = twint.Config()
    c.Username = username
    c.Output = "user_info.txt"
    try:
        twint.run.Lookup(c)
        f = open('user_info.txt')
        user_info = f.readline()
        user_data = user_info.split(' | ')
        f.close()
        os.remove('user_info.txt')
        return user_data
    except:
        print('Sorry, we could not find this user')
        return []
