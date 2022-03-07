import twint
import nest_asyncio
import os

def isVerified(username):
    nest_asyncio.apply()

    c = twint.Config()
    c.Username = username
    c.Output = "user_info.txt"
    try:
        twint.run.Lookup(c)
        f = open('user_info.txt')
        user_info = f.readline()
        f.close()
        os.remove('user_info.txt')
        return 'Verified: True' in user_info
    except:
        print('Sorry, we could not find this user')
        return False
