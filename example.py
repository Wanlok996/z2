import re
import sys

from zhopenie.extractor import Extractor

extr = False  # 是否提取三元组
people = True  # 人员信息#
stru = True


# 提取文书各部分flag

def main(argv):
    extractor = Extractor()
    extractor.load()

    file2 = "./ccc/"
    list13 = extractor.resolveJson3(file2)

    num = 1
    for file in list13:
        f = [file]
        list15 = extractor.findmodel1(f)
        name = list15[0]
        text = list15[1]
        pos_list = list15[2]

        print(name)

        canpan = {}
        typeflag = False
        type = ['判决', '裁定', '调解', '决定', '通知', '令']

        if list15[3] in type:
            print('类型:' + list15[3])
            canpan['类型'] = list15[3]
            canpan['id'] = list15[4]
            if list15[3] == '判决' or list15[3] == '裁定':
                typeflag = True

        name = ['一审', '二审', '终审']

        for t in name:
            pattern = '(\w+)' + t
            m = re.findall(pattern, list15[0])
            if len(m) > 0:
                print(t)
                canpan['审判书'] = t
                break
            else:
                print('一审')
                canpan['审判书'] = '一审'

        if stru:
            print('首部：')
            print(text[0:pos_list[0]])
            print('事实：')
            canpan['事实'] = text[pos_list[0]:pos_list[1]]
            print(text[pos_list[0]:pos_list[1]])
            print('理由：')
            canpan['理由'] = text[pos_list[1]:pos_list[2]]
            print(text[pos_list[1]:pos_list[2]])
            print('结果:')
            canpan['判决结果'] = text[pos_list[2]:-1]
            print(text[pos_list[2]:-1])

            # input()

        peo_inf = {}  # 人员信息
        if people and typeflag:
            f = [text[0:pos_list[0]]]
            peo_inf = extractor.spw(f)
            # print("hhhh",peo_inf)
            for key in peo_inf:
                canpan[key] = peo_inf[key]
        import json
        with open("json/" + str(num) + ".json", "w") as f:
            # json.dump(dict_var, f)  # 写为一行
            json.dump(canpan, f, indent=2, sort_keys=True, ensure_ascii=False)
        num = num + 1

    extractor.release()


if __name__ == "__main__":
    main(sys.argv)
