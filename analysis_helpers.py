import re
from collections import Counter
from config import morph ,russian_stopwords ,positive_words ,negative_words ,emoji
def normalize_text (text ):
    if not isinstance (text ,str ):
        return []
    text =re .sub (r'[^\w\s]','',text ,flags =re .UNICODE ).lower ()
    tokens =text .split ()
    if morph :
        lemma_tokens =[]
        for t in tokens :
            p =morph .parse (t )
            lemma_tokens .append (p [0 ].normal_form if p else t )
        return lemma_tokens
    else :
        return tokens
def analyze_sentiment (text ):
    tokens =normalize_text (text )
    if not tokens :
        return 'neutral'
    pos_score =sum (1 for tok in tokens if tok in positive_words )
    neg_score =sum (1 for tok in tokens if tok in negative_words )
    if pos_score >neg_score :
        return 'positive'
    elif neg_score >pos_score :
        return 'negative'
    else :
        return 'neutral'
def get_emoji_stats (texts_series ,top_n =15 ):
    if emoji is None or texts_series .empty :
        return Counter ()
    all_emojis_list =[]
    for text in texts_series .dropna ():
        if not isinstance (text ,str ):
            continue
        for char_emoji_data in emoji .analyze (text ):
            all_emojis_list .append (char_emoji_data .chars )
    return Counter (all_emojis_list ).most_common (top_n )