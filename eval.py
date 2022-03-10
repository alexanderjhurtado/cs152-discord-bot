from message_processor import MessageProcessor
import pandas as pd
import time


df = pd.read_csv('ben_shapiro_tweets.csv')

mp = MessageProcessor()

scores = []
for i in range(500):
    time.sleep(1)
    scores.append(mp.eval_text(df['tweet'][i]))

scores_df = pd.DataFrame(scores)
scores_df.to_csv('tweet_scores.csv')

scores_df = pd.read_csv('tweet_scores.csv')
def func(row):
    return row['SEXUALLY_EXPLICIT'] > 0.8 or row['SEVERE_TOXICITY'] > 0.8 or row['THREAT'] > 0.8 or row[
        'TOXICITY'] > 0.8 or row['IDENTITY_ATTACK'] > 0.8

scores_df['LABEL'] = scores_df.apply(lambda row: func(row), axis=1)

count = 0
c2 = 0
for i in range(500):
    if scores_df['LABEL'][i]:
        init_entities = mp.eval_entities(df['tweet'][i])
        entities = init_entities[0]
        count += 1 if 'Ben Shapiro' in entities or '@benshapiro' in entities or 'ben shapiro' in entities or 'ben shapiro\'s' in entities else 0
        if 'Ben Shapiro' in entities or '@benshapiro' in entities or 'ben shapiro' in entities or 'ben shapiro\'s' in entities:
            pass
        else:
            print(init_entities)
        c2 += 1
print(count)
print(c2)
