import requests
import spacy
import json
import math
from uni2ascii import uni2ascii

ENTITY_SCORE_THRESHOLD = 10
PERSPECTIVE_SCORE_THRESHOLD = 0.8
# TF_IDF_SURFACING_THRESHOLD = 0.08
# HARASSMENT_SCORE_THRESHOLD = 0.5 # TODO: MODIFY TO ACTUAL VALUE

ABUSIVE_MESSAGE_COUNT_THRESHOLD = 5

class MessageProcessor:
    def __init__(self):
        with open('tokens.json') as f:
            self.perspective_key = json.load(f)['perspective']
        self.named_entity_model = spacy.load('en_core_web_sm')
        self.user_to_abusive_messages = {}
        self.num_total_messages = 0
        self.token_document_frequency = {}
        self.abused_entity_scores = {}
        self.entity_mentions = {}

    # def process_message(self, message):
    #     perspective_scores = self.eval_text(message)
    #     entity_set, tokenized_message = self.eval_entities(message)
    #     self.update_token_document_frequency(tokenized_message)
    #     if any(score >= INDIVIDUAL_SCORE_THRESHOLD for score in perspective_scores.values()):
    #         targeted_entities = self.update_targeted_entities(entity_set, perspective_scores, message, tokenized_message)
    #         for entity_obj in targeted_entities:
    #             entity = entity_obj['name']
    #             mentions = entity_obj['mentions']
    #             tf_idf_scores = self.compute_tf_idf_by_token(mentions)
    #             return [token for token, score in tf_idf_scores.items() if score > TF_IDF_SURFACING_THRESHOLD]

    # public method
    def process_message(self, message):
        user = message.author
        message_content = uni2ascii(message.content)
        perspective_scores = self.eval_text(message_content)
        entity_set, tokenized_message = self.eval_entities(message_content)
        self.update_message_and_entity_ledgers(message, perspective_scores, entity_set, tokenized_message)
        if any(score >= PERSPECTIVE_SCORE_THRESHOLD for score in perspective_scores.values()):
            self.user_to_abusive_messages[user] = self.user_to_abusive_messages.get(user, []) + [message]

    def user_abuse_threshold_exceeded(self):
        users_exceeding_threshold = []
        for user, messages in self.user_to_abusive_messages.items():
            if len(messages) % ABUSIVE_MESSAGE_COUNT_THRESHOLD == 0:
                users_exceeding_threshold.append((user, messages))
        return users_exceeding_threshold

    def entity_abuse_threshold_exceeded(self):
        entities_exceeding_threshold = []
        for entity, harassment_score in self.abused_entity_scores.items():
            if harassment_score >= ENTITY_SCORE_THRESHOLD:
                mentions = self.entity_mentions[entity]
                entities_exceeding_threshold.append((entity, mentions))
                self.abused_entity_scores[entity] = 0
        return entities_exceeding_threshold

    # private methods
    def eval_text(self, message):
        '''
        Given a message string, forwards the message to Perspective and returns a dictionary of scores.
        '''
        PERSPECTIVE_URL = 'https://commentanalyzer.googleapis.com/v1alpha1/comments:analyze'
        url = PERSPECTIVE_URL + '?key=' + self.perspective_key
        data_dict = {
            'comment': {'text': message},
            'languages': ['en'],
            'requestedAttributes': {
                                    'SEVERE_TOXICITY': {}, 'IDENTITY_ATTACK': {},
                                    'THREAT': {}, 'TOXICITY': {}, 'SEXUALLY_EXPLICIT': {},
                                },
            'doNotStore': True
        }
        response = requests.post(url, data=json.dumps(data_dict))
        response_dict = response.json()
        scores = {}
        for attr in response_dict["attributeScores"]:
            scores[attr] = response_dict["attributeScores"][attr]["summaryScore"]["value"]
        return scores

    def eval_entities(self, message):
        '''
        Given a message string, evaluate the text for named entities and returns a set of their referred names.
        '''
        named_entities = set()
        entity_doc = self.named_entity_model(message)
        for entity in entity_doc.ents:
            if entity.label_ == "PERSON" or entity.label_ == "NORP":
                named_entities.add(entity.text)
        return named_entities, [token.text for token in entity_doc]

    def update_message_and_entity_ledgers(self, message, perspective_scores, entity_set, tokenized_message):
        self.update_message_ledger(tokenized_message)
        self.update_targeted_entities(entity_set, perspective_scores, message, tokenized_message)

    def update_message_ledger(self, tokenized_message):
        self.num_total_messages += 1
        for token in set(tokenized_message):
            self.token_document_frequency[token] = self.token_document_frequency.get(token, 0) + 1

    def update_targeted_entities(self, entity_set, perspective_scores, message, tokenized_message):
        '''
        Given a set of entities and the Perspective scores of their originator message, update each entity's
        targeted harassment score and return a list of entities whose harassment score is greater than some threshold
        -- this collection represents the entities who are being targeted with harasssment. This method also logs
        each message the mentions any entity.
        '''
        for entity in entity_set:
            curr_score = self.abused_entity_scores.get(entity, 0)
            curr_score += self.threshold_get(perspective_scores, 'SEVERE_TOXICITY')
            curr_score += self.threshold_get(perspective_scores, 'TOXICITY')
            curr_score += self.threshold_get(perspective_scores, 'IDENTITY_ATTACK')
            curr_score += self.threshold_get(perspective_scores, 'THREAT')
            self.abused_entity_scores[entity] = curr_score
            self.entity_mentions[entity] = self.entity_mentions.get(entity, []) + [{
                'original_message': message,
                'tokenized_message': tokenized_message,
            }]

    def threshold_get(self, dictionary, key, threshold=PERSPECTIVE_SCORE_THRESHOLD):
        '''
        Returns 1 as long as the value of the given key in the given dictionary is at least the given threshold.
        If the value is not at least the threshold, then this method will return 0.
        '''
        return 1 if dictionary[key] >= threshold else 0

    # def compute_tf_idf_by_token(self, target_messages):
    #     num_total_tokens = 0
    #     token_freq = {}
    #     for mention_obj in target_messages:
    #         for token in mention_obj['tokenized_message']:
    #             token_freq[token] = token_freq.get(token, 0) + 1
    #             num_total_tokens += 1
    #     tf_idf_scores = {}
    #     for token, freq in token_freq.items():
    #         tf_idf_scores[token] = (freq / num_total_tokens) * math.log(self.num_total_messages / self.token_document_frequency[token])
    #     return tf_idf_scores
