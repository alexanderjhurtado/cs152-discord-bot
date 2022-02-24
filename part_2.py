import requests
import spacy
import json
import math

TOTAL_SCORE_THRESHOLD = 7.5
INDIVIDUAL_SCORE_THRESHOLD = 0.625
TF_IDF_SURFACING_THRESHOLD = 0.08
HARASSMENT_SCORE_THRESHOLD = 0.5 # TODO: MODIFY TO ACTUAL VALUE

class TargetedEntityDetector:
    def __init__(self):
        with open('tokens.json') as f:
            self.perspective_key = json.load(f)['perspective']
        self.named_entity_model = spacy.load('en_core_web_sm')
        self.entity_scores = {}
        self.entity_mentions = {}
        self.num_total_messages = 0
        self.token_document_frequency = {}

    def process_message(self, message):
        perspective_scores = self.eval_text(message)
        entity_set, tokenized_message = self.eval_entities(message)
        self.update_token_document_frequency(tokenized_message)
        if any(score >= INDIVIDUAL_SCORE_THRESHOLD for score in perspective_scores.values()):
            targeted_entities = self.update_targeted_entities(entity_set, perspective_scores, message, tokenized_message)
            for entity_obj in targeted_entities:
                entity = entity_obj['name']
                mentions = entity_obj['mentions']
                tf_idf_scores = self.compute_tf_idf_by_token(mentions)
                return [token for token, score in tf_idf_scores.items() if score > TF_IDF_SURFACING_THRESHOLD]


    def eval_reported_message(self, message):
        perspective_scores = self.eval_text(message)
        targeted_entities = self.identify_targeted_entities(threshold=TOTAL_SCORE_THRESHOLD)
        _, tokenized_message = self.eval_entities(message)
        identified_harassment_entities = []
        for entity_obj in targeted_entities:
            entity = entity_obj['name']
            if entity in tokenized_message:
                identified_harassment_entities.append(entity_obj)
        return perspective_scores, identified_harassment_entities


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

    def update_token_document_frequency(self, tokenized_message):
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
            curr_score = self.entity_scores.get(entity, 0)
            curr_score += self.threshold_get(perspective_scores, 'SEVERE_TOXICITY', INDIVIDUAL_SCORE_THRESHOLD)
            curr_score += self.threshold_get(perspective_scores, 'TOXICITY', INDIVIDUAL_SCORE_THRESHOLD)
            curr_score += self.threshold_get(perspective_scores, 'IDENTITY_ATTACK', INDIVIDUAL_SCORE_THRESHOLD)
            curr_score += self.threshold_get(perspective_scores, 'THREAT', INDIVIDUAL_SCORE_THRESHOLD)
            self.entity_scores[entity] = curr_score
            self.entity_mentions[entity] = self.entity_mentions.get(entity, []) + [{
                'original_message': message,
                'tokenized_message': tokenized_message,
            }]
        return self.identify_targeted_entities(threshold=TOTAL_SCORE_THRESHOLD)

    def identify_targeted_entities(self, threshold):
        '''
        Determines the set of entities whose total harassment score is greater than the given threshold and returns
        those entities as a list. This list represents the set of entities who are being targeted with harassment.
        '''
        targeted_entities = []
        for entity, harassment_score in self.entity_scores.items():
            if harassment_score >= threshold:
                mentions = self.entity_mentions[entity]
                targeted_entities.append({
                    'name': entity,
                    'total_harassment_score': harassment_score,
                    'avg_harassment_score': float(harassment_score / len(mentions)),
                    'mentions': mentions, })
        return targeted_entities

    def threshold_get(self, dictionary, key, threshold):
        '''
        Grabs the value of the given key from the given dictionary as long as that value is at least the given threshold.
        If the value is not at least the threshold, then this method will return 0.
        '''
        return dictionary[key] if dictionary[key] >= threshold else 0

    def compute_tf_idf_by_token(self, target_messages):
        num_total_tokens = 0
        token_freq = {}
        for mention_obj in target_messages:
            for token in mention_obj['tokenized_message']:
                token_freq[token] = token_freq.get(token, 0) + 1
                num_total_tokens += 1
        tf_idf_scores = {}
        for token, freq in token_freq.items():
            tf_idf_scores[token] = (freq / num_total_tokens) * math.log(self.num_total_messages / self.token_document_frequency[token])
        return tf_idf_scores
