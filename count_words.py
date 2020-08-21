import csv

out = open('split.csv', 'r', encoding='utf8')
f = csv.reader(out)

word_count = []
for line in f:
    text = line[1]
    text = text.split(' ')
    w_count = {}
    for word in text:
        if word in w_count:
            w_count[word] += 1
        else:
            w_count[word] = 1
    word_count.append(w_count)

out.close()
import pickle

ff = open('word_count.pkl', 'wb')
pickle.dump(word_count, ff)
ff.close()
