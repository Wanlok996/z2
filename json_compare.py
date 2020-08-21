import json

from fuzzywuzzy import fuzz

with open("0.json") as f:
    data1 = json.load(f)

with open("00.json") as f:
    data2 = json.load(f)

if data1['类型'] != data2['类型']:
    print('类型不一致')

if data1['审判'] != data2['审判']:
    print('两审终审不一致')


def compare(dict1, dict2, string):
    d1 = dict1[string]
    d2 = dict2[string]
    s = fuzz.partial_ratio(d1, d2)
    if s < 90:
        print(string + '不一致')


compare(data1, data2, '事实')
compare(data1, data2, '理由')
compare(data1, data2, '判决结果')

keywords = ['类型', '审判', '事实', '理由', '判决结果']

for key in data1:
    if key not in keywords:
        if key not in data2:
            print('案件人员姓名' + key + '不一致')
        else:
            if data1[key] != data2[key]:
                print('案件人员信息不一致')
                print('文件1为:' + key + '：' + data1[key])
                print('文件2为:' + key + '：' + data2[key])
