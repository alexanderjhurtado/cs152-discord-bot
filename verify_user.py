import twint
import nest_asyncio
import os

async def isVerified(username):
    nest_asyncio.apply()

    c = twint.Config()
    c.Username = username
    c.Output = "user_info.txt"
    try:
        twint.run.Lookup(c)
        f = open('user_info.txt')
        user_info = f.readline()
        print(user_info)
        f.close()
        os.remove('user_info.txt')
        return True, 'Verified: True' in user_info
    except:
        print('Sorry, we could not find this user')
        return False, False
