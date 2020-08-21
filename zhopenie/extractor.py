# -*- coding: utf-8 -*-
import itertools
import json
import os
import re
from collections import defaultdict

import jieba
import jieba.analyse
import jieba.posseg as pseg
from pyltp import NamedEntityRecognizer
from pyltp import Parser
from pyltp import Postagger
from pyltp import Segmentor
from pyltp import SementicRoleLabeller
from pyltp import SentenceSplitter

from zhopenie.triple import Entity
from zhopenie.triple import Relation
from zhopenie.triple import Triple


class Extractor():

    def __init__(self):
        self.__clause_list = []
        self.__subclause_dict = {}
        self.__triple_list = []
        self.__segmentor = Segmentor()
        self.__postagger = Postagger()
        self.__recognizer = NamedEntityRecognizer()
        self.__parser = Parser()
        self.__labeller = SementicRoleLabeller()
        self.__words_full_list = []
        self.__netags_full_list = []

    @property
    def clause_list(self):
        return self.__clause_list

    @property
    def triple_list(self):
        return self.__triple_list

    def split(self, words, postags):
        start = 0
        for j, w in enumerate(words):
            if w == ',' or w == '，' or w == '。':
                clause = Clause(start, j - 1)
                self.__clause_list.append(clause)
                start = j + 1

        for clause in self.__clause_list:
            clause.split(postags)
            for subclause in clause.sub_clause_list:
                self.add_inverted_idx(subclause)

    def add_inverted_idx(self, subclause):
        for i in range(subclause.start_idx, subclause.end_idx):
            self.__subclause_dict[i] = subclause

    def load(self):

        self.__segmentor.load_with_lexicon('ltp_data/cws.model', 'ltp_data/dict.txt')
        self.__postagger.load('ltp_data/pos.model')
        self.__recognizer.load('ltp_data/ner.model')
        self.__parser.load('ltp_data/parser.model')
        self.__labeller.load('ltp_data/pisrl_win.model')

    def release(self):
        self.__segmentor.release()
        self.__postagger.release()
        self.__recognizer.release()
        self.__parser.release()
        self.__labeller.release()

    def clear(self):
        self.__triple_list = []
        self.__words_full_list = []
        self.__netags_full_list = []

    def resolve_conference(self, entity):
        try:
            e_str = entity.get_content_as_str()
        except Exception:
            return '?'
        ref = e_str
        if e_str == '他' or e_str == '她':
            for i in range(entity.loc, -1, -1):
                if self.__netags_full_list[i].lower().endswith('nh'):
                    ref = self.__words_full_list[i]
                    break
        return ref

    def resolve_all_conference(self):
        for t in self.triple_list:
            e_str = self.resolve_conference(t.entity_1)
            try:
                t.entity_1.content = e_str.split()
            except Exception:
                pass

    def chunk_str(self, data):
        sents = SentenceSplitter.split(data)
        offset = 0
        for sent in sents:
            try:

                # words = self.__segmentor.segment(sent)
                words = jieba.cut(sent)
                words = " ".join(words).split(" ")
                # postags = self.__postagger.postag(words)

                postags = list(pseg.cut(sent))
                tags = [x.flag for x in postags]
                words = [x.word for x in postags]
                netags = self.__recognizer.recognize(words, tags)
                # print(words)
                # print(list(netags))
                arcs = self.__parser.parse(words, tags)
                # print("\t".join("%d:%s" % (arc.head, arc.relation) for arc in arcs))
                roles = self.__labeller.label(words, tags, netags, arcs)
                self.chunk_sent(list(words), list(tags), list(arcs), offset)
                offset += len(list(words))
                self.__words_full_list.extend(list(words))
                self.__netags_full_list.extend(list(netags))
            except Exception as e:
                print(str(e))
                pass

    def chunk_sent(self, words, postags, arcs, offset):
        root = [i for i, x in enumerate(arcs) if x.relation == 'HED']
        if len(root) > 1:
            raise Exception('More than 1 HEAD arc is detected!')
        root = root[0]
        relations = [i for i, x in enumerate(arcs) if x.head == root and x.relation == 'COO']
        relations2 = [i for i, x in enumerate(postags) if x == 'v']
        relations.insert(0, root)
        relations = relations + relations2
        relations = list(set(relations))
        prev_e1 = None
        e1 = None
        for rel in relations:

            left_arc = [i for i, x in enumerate(arcs) if x.head == rel and x.relation == 'SBV']

            if len(left_arc) > 1:
                name = []
                loc = find_farthest_att(arcs, left_arc[0])
                for arc in left_arc:
                    leftmost = find_farthest_att(arcs, arc)
                    name += [words[i] for i in range(leftmost, arc + 1)]

                e1 = Entity(1, name, offset + leftmost)

                # raise Exception('More than 1 left arc is detected!')
            elif len(left_arc) == 0:
                e1 = prev_e1
            elif len(left_arc) == 1:
                left_arc = left_arc[0]
                leftmost = find_farthest_att(arcs, left_arc)
                e1 = Entity(1, [words[i] for i in range(leftmost, left_arc + 1)], offset + leftmost)

            prev_e1 = e1

            right_arc = [i for i, x in enumerate(arcs) if x.head == rel and x.relation == 'VOB']

            e2_list = []
            if not right_arc:
                e2 = Entity(2, None)
                e2_list.append(e2)
            else:
                right_ext = find_farthest_vob(arcs, right_arc[0])

                items = [i for i, x in enumerate(arcs) if x.head == right_ext and x.relation == 'COO']
                items = right_arc + items

                count = 0
                for item in items:
                    leftmost = find_farthest_att(arcs, item)

                    e2 = None

                    if count == 0:
                        e2 = Entity(2, [words[i] for i in range(leftmost, right_ext + 1)], offset + leftmost)
                    else:
                        p1 = range(leftmost, right_arc[0])
                        p2 = range(item, find_farthest_vob(arcs, item) + 1)
                        e2 = Entity(2, [words[i] for i in itertools.chain(p1, p2)])

                    e2_list.append(e2)
                    # r = Relation(words[rel])
                    r = [words[rel]]
                    lef_arc = [words[i] for i, x in enumerate(arcs) if x.head == rel and x.relation == 'ADV']
                    # print(lef_arc)
                    # print(words)
                    # lef_ar = [words[i] for i, x in enumerate(arcs) if x.head == 4 and x.relation == 'POB']
                    # print(lef_ar)
                    # if len(lef_ar)>1:
                    # lef_arc=None
                    r = Relation(lef_arc + r)
                    t = Triple(e1, e2, r)
                    self.__triple_list.append(t)
                    count += 1

    # def spli(self, data):
    #   a=0
    #    for j, w in enumerate(data):
    #       if w=="：":
    #            a=j+1
    #    data1=data[a:len(data)]
    #    print(data1)

    def spr(self, data):
        # path = r"C:\Users\Administrator\Desktop\d1.json"
        # file = open(path, "rb")
        # fileJson = json.load(file)
        # casestrcontent = fileJson["casestrcontent"]
        dict1 = {}
        n = data.split('。')
        print(n)
        for i in range((len(n) - 1)):
            print(n[i])
            # m = re.search(r'^(.\w.*?)：(\w*)，?(\w*)',n[i])
            m = re.search(r'(\w*)：(\w*)', n[i])
            # print(m.groups())
            if m != None:
                data1 = m.group(2)
                print(i)
                print('start=', m.start(2))
                print('end=', m.end(2))
                a = m.start(2)
                b = m.end(2)
                postagedata1 = list(pseg.cut(data1))
                # print(postagedata1)
                tags = [x.flag for x in postagedata1]
                print(tags)
                # print(type(tags))
                for p, val in enumerate(tags):
                    if val == 'ns' or val == 'nt' or val == 'n' or val == 'eng' or val == 'm':
                        dict1[data1] = ['ns', i]
                        break
                    else:
                        dict1[data1] = ['nr', i]
                print(dict1)

    def resolveJson3(self, filename):
        list13 = []
        for info in os.listdir(filename):
            # print(info)
            domain = os.path.abspath(filename)
            inf = os.path.join(domain, info)
            path = inf
            file = open(path, "r", encoding="utf-8")
            data = json.load(file)
            casename = data["casename"]
            casecontent = data["casecontent"]
            casestrcontent = casecontent["casestrcontent"]

            # list13.append([casename, casestrcontent])
            casedocid = data["casedocid"]

            casetype = data["casedoctype"]
            list13.append([casename, casestrcontent, casedocid, casetype])
        return (list13)  # 一篇文档的地址

    def findmodel1(self, list13):  # 找出首部    list13为一篇文档的地址
        list15 = []
        for i in range(len(list13)):
            name = list13[i][0]
            # print(name)
            text = list13[i][1]

            id = list13[i][2]
            type = list13[i][3]
            # print(text)
            pos_list = []
            headers = []
            countnumber = []
            if "判决" == type:
                headers = ["现已审查终结", "现已审理终结", "现已缺席审理终结", "本院依法缺席审理", "已审理完毕"]
                reasons = ["本院认为"]
                enddings = ["判决如下"]
            elif "裁定" == type:
                headers = ["现已审查终结", "现已审理终结", "已审理完毕", "撤诉申请", "向本院申请撤回", "向本院提出撤回",
                           "向本院申请撤销", "自愿撤诉", "撤回上诉", "提起上诉", "依法进行审理", "复议申请", "终结本次执行程序", "本院依法受理"
                    , "申请撤诉", "审查完毕", "撤回起诉"]
                reasons = ["本院认为", "本院经审查认为"]
                enddings = ["裁定如下"]
            elif "决定" == type:
                headers = ["向本院申请复议"]
                reasons = ["经审查"]
                enddings = ["决定如下"]
            elif "通知" == type:
                headers = ["现已审查终结", "现已复查完毕", "向本院申诉", "向本院提出申诉"]
                reasons = ["本院经审查认为", "本院经复查认为", "本院审查认为", "本院经审查", "经审查", "本院认为"]
                enddings = ["特此通知"]
            elif "令" == type:
                headers = ["向本院申请复议"]
                reasons = ["本院认为"]
                enddings = ["判决如下"]
            # else:
            #     os.system('copy ' + list11[i] + ' E:\casedatas')
            #     print("不可处理")

            for header in headers:
                aa = text.count(header)
                countnumber.append(aa)

            a = b = c = 0
            for header in headers:

                a = text.find(header)
                if a != -1:
                    # 添加部分
                    a = a + len(header) + 1
                    break

            for reason in reasons:
                bb = text.count(reason)
                countnumber.append(bb)
            for reason in reasons:
                b = text.find(reason)
                if b != -1:
                    break

            for endding in enddings:
                cc = text.count(endding)
                countnumber.append(cc)
            for endding in enddings:
                c = text.find(endding)
                if c != -1:
                    break

            if a == -1 and b != -1:
                pos_list.append(b)
                pos_list.append(b)
                pos_list.append(c)
                # listnew = list13[i][2]
            elif a > b and b != -1:
                pos_list.append(b)
                pos_list.append(b)
                pos_list.append(c)
                # listnew = list13[i][2]
                # 该种情况需要处理
            elif b == -1:
                pos_list.append(c)
                pos_list.append(c)
                pos_list.append(c)
                # print("hhh")
                # listnew=list13[i][2]

            else:
                pos_list.append(a)
                pos_list.append(b)
                pos_list.append(c)

            pos_list.append(len(text))

            list15 = [name, text, pos_list, type, id]
            # print(name)
            # input()
            # print(listnew)

        return list15

    def spw(self, list15):  # 一篇首部中 {人名：身份}  “ ：”
        dict1 = defaultdict(list)

        dict2 = {}

        keywords = []
        wordlist = []
        simp = {}  # 简称
        with open('dict1.txt', 'r') as f:
            for word in f:
                word = word.strip('\n')
                if word == '申请人' or word == '上诉人':
                    word = '[^被]' + word
                keywords.append(word)

        for i in range(len(list15)):

            n = re.split(r'[，。]', list15[i])
            # print(n)
            # name=list15[i][0]
            for j in range(len(n)):
                nl = n[j]
                if '本院' in nl:
                    break
                pattern = '^系(\w)'
                m = re.findall(pattern, nl)
                if len(m) > 0:
                    continue
                for word in keywords:
                    namelist = []
                    pattern = '\w+（\w+' + word + '人*' + '）(\w*)' + '|' + '\w+（\w+' + word + '人*' + '）：(\w*)'
                    # namelist=copy.deepcopy(dict1[word])
                    for v in dict1[word]:
                        val = v[0]
                        if val not in namelist:
                            namelist.append(val)
                        if val in simp:
                            if simp[val] not in namelist:
                                namelist.append(simp[val])

                    namelist += keywords
                    m = re.findall(pattern, nl)
                    if len(m) != 0:
                        for l in m:
                            data1 = ''
                            for dat in l:
                                if dat != '':
                                    flag = True
                                    for name in namelist:
                                        pattern = name + '(\w*)'
                                        p = re.findall(pattern, dat)
                                        if len(p) > 0:
                                            flag = False
                                    if flag:
                                        data1 = dat
                                        wordlist.append(dat)

                            postagedata1 = list(pseg.cut(data1))

                            tags = [x.flag for x in postagedata1]

                            for p, val in enumerate(tags):
                                if val == 'ns' or val == 'nt' or val == 'n' or val == 'eng' or val == 'm' or val == 'x':
                                    dict1[word].append([data1, 'ns'])
                                    break
                                else:
                                    dict1[word].append([data1, 'nr'])
                nl = re.sub(u"（.*?）", "", n[j])
                for word in keywords:
                    namelist = []
                    pattern = '\w*' + word + '人*' + '：(\w*)' + '|\w*' + word + '人*' + ':(\w*)' + '|' + '\w*' + word + '人*' + '(\w*)'

                    for v in dict1[word]:
                        val = v[0]
                        if val not in namelist:
                            namelist.append(val)
                        if val in simp:
                            if simp[val] not in namelist:
                                namelist.append(simp[val])

                    namelist += keywords
                    m = re.findall(pattern, nl)
                    if len(m) != 0:
                        for l in m:
                            data1 = ''
                            for dat in l:
                                if dat != '':
                                    flag = True
                                    for name in namelist:
                                        pattern = '(' + name + '\w*)'
                                        p = re.findall(pattern, dat)
                                        if len(p) > 0:
                                            flag = False
                                    if flag:
                                        pattern = '\w*(到庭)\w*|\w*(本院)\w*'
                                        m = re.findall(pattern, dat)
                                        if len(m) == 0:
                                            data1 = dat
                                            wordlist.append(dat)

                            postagedata1 = list(pseg.cut(data1))

                            tags = [x.flag for x in postagedata1]

                            w2 = word.replace('[^被]', '')
                            for p, val in enumerate(tags):
                                if val == 'ns' or val == 'nt' or val == 'n' or val == 'eng' or val == 'm' or val == 'x':

                                    dict1[w2].append([data1, 'ns'])
                                    break
                                else:
                                    dict1[w2].append([data1, 'nr'])

                for word in wordlist:
                    pattern = word + '（\w*' + '简称' + '(\w+)）'

                    m = re.findall(pattern, nl)
                    if len(m) != 0:
                        for name in m:
                            simp[word] = name

            clearlist = []
            for word in dict1:
                if len(dict1[word]) == 0:
                    clearlist.append(word)
            for v in clearlist:
                dict1.pop(v, [])
            print(dict1)

            print('人员信息')
            n = re.split(r'[。]', list15[i])

            for key in dict1:
                for value in dict1[key]:
                    p1 = '^' + key + '人*?' + value[0] + '(.+)'
                    p2 = '[^被]' + key + '人*?' + value[0] + '(.+)'
                    p3 = '^' + key + '人*?' + '：' + value[0] + '(.+)'
                    p4 = '[^被]' + key + '人*?' + '：' + value[0] + '(.+)'

                    plist = [p1, p2, p3, p4]
                    flag = False
                    for j in range(len(n)):
                        nl = n[j]
                        for p in plist:
                            m = re.findall(p, nl)
                            if len(m) > 0:
                                for v in m:
                                    if v != '':
                                        pattern = '\w*(到庭)\w*|\w*(本院)\w*'
                                        m = re.findall(pattern, v)
                                        if len(m) > 0:
                                            continue
                                        matchObj = re.match(r'，(.*)', v)
                                        if matchObj:
                                            v = matchObj.group(1)
                                        else:
                                            matchObj = re.match(r'^（(.*)）$', v)
                                            if matchObj:
                                                v = matchObj.group(1)

                                        dict2[key + value[0]] = v
                                        print(value[0] + ':')
                                        print(v)
                                        flag = True
                                        break
                                if flag:
                                    break
                        if flag:
                            break

            # input()
            return dict2


def find_farthest_att(arcs, loc):
    att = [i for i, x in enumerate(arcs) if x.head == loc and (x.relation == 'ATT' or x.relation == 'SBV')]
    if not att:
        return loc
    else:
        return find_farthest_att(arcs, min(att))


def find_farthest_vob(arcs, loc):
    vob = [i for i, x in enumerate(arcs) if x.head == loc and x.relation == 'VOB']
    if not vob:
        return loc
    else:
        return find_farthest_vob(arcs, max(vob))


class Clause(object):

    def __init__(self, start=0, end=0):
        self.start_idx = start
        self.end_idx = end
        self.__sub_clause_list = []

    @property
    def sub_clause_list(self):
        return self.__sub_clause_list

    def __str__(self):
        return '{} {}'.format(self.start_idx, self.end_idx)

    def split(self, postags):
        start = self.start_idx
        for k, pos in enumerate(postags):
            if k in range(self.start_idx, self.end_idx + 1):
                if pos == 'c':
                    subclause = SubClause(start, k - 1)
                    self.__sub_clause_list.append(subclause)
                    start = k + 1


class SubClause():

    def __init__(self, start=0, end=0):
        self.start_idx = start
        self.end_idx = end
