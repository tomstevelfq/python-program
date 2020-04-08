# -*- coding: utf-8 -*-
import sys
import os
import urllib.request
import json
import time
from bs4 import BeautifulSoup
import xlrd
import xlwt
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib as mpl
import numpy as np
from jieba.analyse import extract_tags
import jieba
from wordcloud import WordCloud
import math

TIME_OUT_SETTING = 5  #单位为秒
RETRY_TIMES = 3 #失败重试次数
RETRY_WAITING_TIME = 1 #失败后重试等待时长，单位秒
WEB_SITE_CHARSETTING = "GBK"  #当当网采用GBK编码
IN_PATH = "in"
OUT_PATH = "out"
URL_FILENAME = "url.txt"


#工具函数定义开始======================================

#函数功能字符串转整数，处理了异常，异常时返回缺省值
def toInt(inStr:str, default_val:int=0):
    try:
        int_val = int(inStr)
        return int_val
    except:
        return default_val


#工具函数定义结束======================================


# Book类说明：
# BooK对应当当网书实体。
# Book类实现通过当当网书籍链接获取书籍信息功能。
# 其中categoryPath参数在获取书籍对应的评论时需要使用。
class Book(object):
    def __init__(self):
        self.__bookName__ = ""     #书名
        self.__productID__ = ""    #书对应的产品ID
        self.__subName__ = ""      #书对应的简述
        self.__url__ = ""          #书对应的URL
        self.__categoryPath__ = "" #书分类路径 （重要，获取评论信息时需要使用）
        self.__categoryId__ = ""   #书分类ID
        self.__eBookID__ = ""      #书书EBOOKID

    def getBookName(self):
        return self.__bookName__

    def getProductID(self):
        return self.__productID__

    def getsubName(self):
        return self.__subName__

    def getBookURL(self):
        return self.__url__

    def getCategoryPath(self):
        return self.__categoryPath__

    def getCategoryID(self):
        return self.__categoryId__

    def getEBookID(self):
        return self.__eBookID__

    def clear(self):
        self.__bookName__ = ""
        self.__productID__ = ""
        self.__subName__ = ""
        self.__url__ = ""
        self.__categoryPath__ = ""
        self.__categoryId__ = ""
        self.__eBookID__ = ""

    def setBookName(self, bookname):
        self.__bookName__ = bookname

    def setProductID(self, pid):
        self.__productID__ = pid

    def setSubName(self, sub_name):
        self.__subName__ = sub_name

    def setBookURL(self, b_url):
        self.__url__ = b_url

    def setCategoryPath(self, categorypath):
        self.__categoryPath__ = categorypath

    def setCategoryID(self, cid):
        self.__categoryId__ = cid

    def setEBookID(self, ebookid):
        self.__eBookID__ = ebookid


    #根据Book链接获取书籍信息
    def loadBookInfo(self, bookurl:str):
        try:
            # 访问书籍网站地址，获取书籍页面信息
            html = urllib.request.urlopen(bookurl, timeout=TIME_OUT_SETTING).read()
            html_str = str(html.decode(WEB_SITE_CHARSETTING))

            # 定位书籍信息数据位置，找到书籍信息json数据
            flag_str = "var prodSpuInfo ="
            start_pos = html_str.find(flag_str)
            html_str = html_str[start_pos + len(flag_str):].strip()
            end_pos = html_str.find("}")
            html_str = html_str[:end_pos + 1].strip()
            book_info = json.loads(html_str)

            # 填写Book类书籍信息
            self.__bookName__ = book_info['productName']
            self.__productID__ = book_info['productId']
            self.__subName__ = book_info['productSubName']
            self.__url__ = book_info['url']
            self.__categoryPath__ = book_info['categoryPath']
            self.__categoryId__ = book_info['categoryId']
            self.__eBookID__ = book_info['eBookId']
            print("获取书籍信息成功。书名：%s, 书籍分类路径：%s, 书籍ID: %s, URL(%s)" % (self.__bookName__, self.__categoryPath__,
                                                           self.__productID__, self.__url__))
            return 0
        except:
            self.clear()
            return -1

    #生成获取数据评论链接模板
    def getBookCommentBaseURL(self):
        url_head = "http://product.dangdang.com/index.php?r=comment%2Flist&productId="
        url_mid_1_str = "&categoryPath="
        url_mid_2_str = "&mainProductId="
        url_tail = "&mediumId=0&pageIndex="
        segment2_str = "&sortType=1&filterType=1&isSystem=1" \
                   "&tagId=0&tagFilterCount=0&template=publish&long_or_short=short"
        return [url_head+self.__productID__+url_mid_1_str+self.__categoryPath__\
               +url_mid_2_str+self.__productID__+url_tail, segment2_str]


# BookComment类说明：
# 记录Comment实体，一条评论，一条BookComment记录
class BookComment(object):
    def __init__(self):
        self.__bookID__ = ""
        self.__comment__ = ""
        self.__comment_time__ = ""
        self.__buyer__ = ""
        self.__buyer_level__ = ""
        self.__score__ = -1

    def setBookID(self, id):
        self.__bookID__ = id

    def setComment(self, commentstr):
        self.__comment__ = commentstr

    def setCommentTime(self, ctime):
        self.__comment_time__ = ctime

    def setBuyer(self, cbuyer):
        self.__buyer__ = cbuyer

    def setBuyerLevel(self, clevel):
        self.__buyer_level__ = clevel

    def setBookScore(self, ival):
        self.__score__ = ival

    def getBookID(self):
        return self.__bookID__

    def getComment(self):
        return self.__comment__

    def getCommentTime(self):
        return self.__comment_time__

    def getBuyer(self):
        return self.__buyer__

    def getBuyerLevel(self):
        return self.__buyer_level__

    def getBookScore(self):
        return self.__score__

    def clear(self):
        self.__bookID__ = ""
        self.__comment__ = ""
        self.__comment_time__ = ""
        self.__buyer__ = ""
        self.__buyer_level__ = ""
        self.__score__ = -1

    def toList(self):
        return [self.__bookID__, self.__buyer__, self.__buyer_level__,
                self.__score__, self.__comment__, self.__comment_time__]


# BookCommentWork类说明：
# BookCommentWork类是实现获取评论数据的主体类
# 支持从网络抓取评论数据
# 支持评论数据保存为excel
# 支持从本地读取excel文件，加载评论数据
class BookCommentWork(object):
    def __init__(self):
        self.__book__ = None
        self.__comments__ = []

    def clear(self):
        self.__book__ = None
        self.__comments__.clear()

    def getBook(self):
        return self.__book__

    def doLoadBookComments(self, bookURL):
        print("开始获取数据评论信息...")
        self.__comments__.clear()
        self.__book__ = Book()

        #根据链接获取数据信息
        iRtn = self.__book__.loadBookInfo(bookURL)

        if iRtn != 0:
            print("获取书籍信息失败，书籍地址(%s)" % bookURL)
            print("任务结束")
            return

        # 获取评论url模板
        comment_baseurl = self.__book__.getBookCommentBaseURL()
        start_index = 1


        while start_index > 0:
            # 生成评论url（每页评论有不同的url，根据url模板和评论页数生成评论url）

            comment_url = comment_baseurl[0] + str(start_index) + comment_baseurl[1]
            page_str = self.__downloadCommentPage__(comment_url)
            if page_str == "":
                print("书籍ID%s （书名：%s）获取第%d页评论失败. 评论URL(%s)"
                      % (self.__book__.getProductID(), self.__book__.getBookName(), start_index, comment_url))
            else:
                comment_info = json.loads(page_str)
                commentPage = comment_info['data']['list']['html']
                comment_data = self.__load_comment_data__(commentPage)
                if len(comment_data) > 0:
                    #当前页有评论数据
                    self.__comments__.extend(comment_data)
                    print("书籍ID%s （书名：%s）获取第%d页评论完成, 评论条数:%d"
                          % (self.__book__.getProductID(), self.__book__.getBookName(), start_index, len(comment_data)))
                    start_index = start_index + 1
                else:
                    # 当前页无评论数据，到达最后一页
                    start_index = -1

        for comment_item in self.__comments__:
            comment_item.setBookID(self.__book__.getProductID())

        print("获取数据评论信息完成，共有评论:%d条" % (len(self.__comments__)))


    def __downloadCommentPage__(self, commentutl):
        curr_times = 0
        while curr_times <= RETRY_TIMES:
            try:
                html = urllib.request.urlopen(commentutl, timeout=TIME_OUT_SETTING).read()
                jsonstr = str(html.decode(WEB_SITE_CHARSETTING))
                return jsonstr
            except:
                print("获取评论失败， URL(%s)" % commentutl)
                curr_times = curr_times + 1
                if curr_times <= RETRY_TIMES:
                    time.sleep(RETRY_WAITING_TIME)
                    print("开始重试：计划重试次数 %d，当前重试次数 %d" % (curr_times, RETRY_TIMES))
        return ""

    def __load_comment_data__(self, pagestr):
        soup = BeautifulSoup(pagestr, 'lxml')
        #定位评论页区块
        content = soup.select('div[class="comment_items clearfix"]')
        #获取评论数据
        comment_count = len(content)
        comment_list = []
        for i in range(comment_count):
            comment_item = self.__gen_comment_item(content[i])
            if not (comment_item is None):
                comment_list.append(comment_item)
        return comment_list

    def __gen_comment_item(self, pageContent):
        commentitem = BookComment()
        # 填写评论分数
        contscore = pageContent.select('em')
        if len(contscore) > 0:
            commentitem.setBookScore(toInt(str(contscore[0].text).strip()[:-1], default_val=-1))
        # 填写评论
        commentstr = pageContent.select('div[class=describe_detail] > span')
        if len(commentstr) > 0:
            commentitem.setComment(str(commentstr[0].text).strip())
        # 填写评论时间
        commenttime = pageContent.select('div[class="starline clearfix"] > span')
        if len(commenttime) > 0:
            commentitem.setCommentTime(str(commenttime[0].text).strip())
        # 填写评论用户和用户级别
        commuser_info = pageContent.select('div[class=items_left_pic] > span')
        if len(commuser_info) > 1:
            commentitem.setBuyer(str(commuser_info[0].text).strip())
            commentitem.setBuyerLevel(str(commuser_info[1].text).strip())
        try:
            print("评论:%s  By(%s:%s)" % (commentitem.getComment(), commentitem.getBuyer(), commentitem.getCommentTime()))
            return commentitem
        except:
            print("评论解码失败，无效评论!")
            return None

    # 将评论数据保存到文件
    # 参数:文件保存路径（文件自动以BOOKID命名）
    def save(self, out_path):
        data_count = len(self.__comments__)

        if data_count == 0:
            print("没有需要存储的评论数据!")
            return

        workbook = xlwt.Workbook(encoding='GBK')
        comment_sheet = workbook.add_sheet("评论数据")
        comment_sheet.write(0, 0, "用户昵称")
        comment_sheet.write(0, 1, "用户级别")
        comment_sheet.write(0, 2, "评论时间")
        comment_sheet.write(0, 3, "分数")
        comment_sheet.write(0, 4, "评论")

        for i in range(data_count):
            comment_item = self.__comments__[i]
            comment_sheet.write(i+1, 0, comment_item.getBuyer())
            comment_sheet.write(i+1, 1, comment_item.getBuyerLevel())
            comment_sheet.write(i+1, 2, comment_item.getCommentTime())
            comment_sheet.write(i+1, 3, str(comment_item.getBookScore()))
            comment_sheet.write(i+1, 4, comment_item.getComment())

        bookinfo_sheet = workbook.add_sheet("书籍信息")
        bookinfo_sheet.write(0, 0, "书籍ID")
        bookinfo_sheet.write(0, 1, self.__book__.getProductID())
        bookinfo_sheet.write(1, 0, "书籍名称")
        bookinfo_sheet.write(1, 1, self.__book__.getBookName())
        bookinfo_sheet.write(2, 0, "书籍副标题")
        bookinfo_sheet.write(2, 1, self.__book__.getsubName())
        bookinfo_sheet.write(3, 0, "书籍URL")
        bookinfo_sheet.write(3, 1, self.__book__.getBookURL())
        bookinfo_sheet.write(4, 0, "书籍分类路径")
        bookinfo_sheet.write(4, 1, self.__book__.getCategoryPath())
        bookinfo_sheet.write(5, 0, "书籍分类ID")
        bookinfo_sheet.write(5, 1, self.__book__.getCategoryID())
        bookinfo_sheet.write(6, 0, "EBookID")
        bookinfo_sheet.write(6, 1, self.__book__.getEBookID())
        bookinfo_sheet.write(7, 0, "评论数")
        bookinfo_sheet.write(7, 1, str(data_count))
        full_out_name = out_path+"/"+self.__book__.getProductID()+".xls"
        workbook.save(full_out_name)
        print("保存评论数据文件完成！文件名：%s" % (full_out_name))

    # 通过本地文件加载评论数据
    # 参数:文件路径, BookID
    def loadfromfile(self, filepath:str, bookID:str):
        fullname = filepath + "/" + bookID + ".xls"
        if (not os.path.isfile(fullname)):
            print("找不到目标文件。文件名：%s" % (fullname))
            return

        self.clear()
        workbook = xlrd.open_workbook(fullname)
        try:
            bookinfo_sheet = workbook.sheet_by_name("书籍信息")
            comment_sheet = workbook.sheet_by_name("评论数据")
        except:
            print("目标文件格式不正确！文件名：%s" % (fullname))
            return

        self.__book__ = Book()
        self.__book__.setProductID(bookinfo_sheet.cell(0, 1).value)
        self.__book__.setBookName(bookinfo_sheet.cell(1, 1).value)
        self.__book__.setSubName(bookinfo_sheet.cell(2, 1).value)
        self.__book__.setBookURL(bookinfo_sheet.cell(3, 1).value)
        self.__book__.setCategoryPath(bookinfo_sheet.cell(4, 1).value)
        self.__book__.setCategoryID(bookinfo_sheet.cell(5, 1).value)
        self.__book__.setEBookID(bookinfo_sheet.cell(6, 1).value)

        data_count = toInt(bookinfo_sheet.cell(7, 1).value)

        if data_count > 0:
            for i in range(data_count):
                commentitem = BookComment()
                commentitem.setBookID(self.__book__.getProductID())
                commentitem.setBuyer(comment_sheet.cell(i+1, 0).value)
                commentitem.setBuyerLevel(comment_sheet.cell(i+1, 1).value)
                commentitem.setCommentTime(comment_sheet.cell(i+1, 2).value)
                commentitem.setBookScore(toInt(comment_sheet.cell(i + 1, 3).value, default_val=-1))
                commentitem.setComment(comment_sheet.cell(i+1, 4).value)
                self.__comments__.append(commentitem)
        print("加载评论数据文件完成！评论数据：%d 条, BookID (%s),书籍名称（%s）"
              % (len(self.__comments__), self.__book__.getProductID(), self.__book__.getBookName()))

    #将评论数据转为Pandas DataFrame形式，可用于分析
    def toPDData(self):
        data_count = len(self.__comments__)
        if data_count > 0:
            all_data = []
            for i in range(data_count):
                all_data.append(self.__comments__[i].toList())
            pd_colums = ['bookid', 'buyer', 'buyer_level', 'score', 'comment', 'comment_time']
            pd_data = pd.DataFrame(data=all_data, columns=pd_colums)
            return pd_data
        else:
            return None

# Wordjudge类说明：
# 用于评论有效性检测
#使用TFIDF方法实现（用了第三方包）
class Wordjudge(object):
    def __init__(self):
        self.__keyword__ = []
        self.__weight__ = []
        self.__allword__ = {}

    def clear(self):
        self.__keyword__.clear()
        self.__weight__.clear()
        self.__allword__.clear()

    def genKeyWord(self, comments_list, topK:int=100, withWeight:bool=True,  manualRate:float=0.0):
        self.clear()

        all_text = ""
        for comment_str in comments_list:
            text_str = str(comment_str).strip()
            seg_list = jieba.cut(text_str)
            for w in seg_list:
                w_str = str(w).strip()
                w_stat = self.__allword__.get(w_str, None)
                if w_stat is None:
                    self.__allword__[w_str] = 1
                else:
                    del self.__allword__[w_str]
                    self.__allword__[w_str] = 1 + w_stat

            all_text = all_text + text_str

        target_top_size = topK
        if manualRate > 0:
            allwordcount = len(self.__allword__)
            target_top_size = math.floor(allwordcount * manualRate)

        for keyword, weight in extract_tags(all_text, topK=target_top_size, withWeight=withWeight):
            self.__keyword__.append(keyword)
            self.__weight__.append(weight)

        return len(self.__keyword__)

    def getallKeyWord(self):
        return self.__keyword__, self.__weight__

    def getallword(self):
        return self.__allword__

    def doCalCommentBadRate(self, comments_list, keywordRate:float=0.01, keywordinComment:int=1):
        self.genKeyWord(comments_list, manualRate=keywordRate)

        result_data = []
        badcomments = []

        for comment_str in comments_list:
            key_word_incomment_count = 0
            text_str = str(comment_str).strip()

            showkeywork = ""
            for keyword in self.__keyword__:
                if text_str.find(keyword) >= 0:
                    key_word_incomment_count = key_word_incomment_count + 1
                    showkeywork = showkeywork + keyword + "|"

            if key_word_incomment_count < keywordinComment:
                badcomments.append(text_str)
            result_data.append([text_str, key_word_incomment_count, showkeywork[:-1]])

        return badcomments, result_data

    def showWordCloud(self, in_dir, out_dir, bookID, word_count:int=0):
        if (word_count) == 0  or (word_count > len(self.__keyword__)):
            text = " ".join(self.__keyword__)
        else:
            text = " ".join(self.__keyword__[:word_count])

        mycloudword = WordCloud(font_path=in_dir+'/simhei.ttf', width=800,
                                height=600, background_color='white').generate(text)
        plt.imshow(mycloudword)
        plt.axis("off")
        mycloudword.to_file(out_dir+"/"+bookID+"_wordcloud.png")
        plt.show()



#对评论扩充评论字数，针对评论字数分布进行分析
def dowordlenanalysis(df_data:pd.DataFrame, out_path, bookid):
    word_len_data = df_data.copy()
    word_len_data['word_length'] = word_len_data['comment'].str.len()
    word_len_data = word_len_data[['buyer', 'buyer_level', 'score', 'word_length']]

    def word_length_type_handler(df):
        length_type = 8
        if df['word_length'] <= 5:
            length_type = 1
        if (df['word_length'] > 5) and (df['word_length'] <= 10):
            length_type = 2
        if (df['word_length'] > 10) and (df['word_length'] <= 15):
            length_type = 3
        if (df['word_length'] > 15) and (df['word_length'] <= 20):
            length_type = 4
        if (df['word_length'] > 20) and (df['word_length'] <= 30):
            length_type = 5
        if (df['word_length'] > 30) and (df['word_length'] <= 40):
            length_type = 6
        if (df['word_length'] > 40) and (df['word_length'] <= 50):
            length_type = 7
        return length_type

    word_len_data['length_type'] = word_len_data.apply(word_length_type_handler, axis=1)
    pd_word_len_type = (word_len_data['length_type'].value_counts()).to_frame(name="datacount")

    mpl.rcParams['font.sans-serif'] = ['SimHei']
    plt.bar(pd_word_len_type.index.tolist(), pd_word_len_type['datacount'].tolist(), alpha=0.5, width=0.3,
            color='yellow', edgecolor='red', label='The First Bar', lw=3)
    plt.xticks(np.arange(1, 9), ('少于5字', '少于10字', '少于15字', '少于20字', '少于30字',
                              '少于40字', '少于50字', '大于50字'), rotation=30)
    plt.xlabel('图1. 评论字数分布', fontsize=10)

    pic_file = out_path + "/" + bookid + "_word_length.png"
    plt.savefig(pic_file)
    plt.show()

    x_data = ['少于5字', '少于10字', '少于15字', '少于20字', '少于30字','少于40字', '少于50字', '大于50字']
    y_data = pd_word_len_type['datacount'].tolist()
    pd_out_word = pd.DataFrame(data={'评论字数':x_data, '评论数量':y_data})
    all_comment = pd_out_word['评论数量'].sum()
    p_rate = [("%.2f" % (x * 100.0 / all_comment))+"%" for x in pd_out_word['评论数量'].tolist()]
    pd_out_word['占比'] = p_rate

    table_file = out_path+"/"+bookid+"_word_length.csv"
    print(pd_out_word)
    pd_out_word.to_csv(table_file, index=None, encoding=WEB_SITE_CHARSETTING)


#针对评论对应打分进行分析
def doscoreanalysis(df_data:pd.DataFrame, out_path, bookid):
    word_score_data = df_data.copy()
    word_score_data['word_length'] = word_score_data['comment'].str.len()
    word_score_data = word_score_data[['buyer', 'buyer_level', 'score', 'word_length']]
    word_score_type_data = (word_score_data['score'].value_counts()).to_frame(name="scorecount")
    word_score_type_data.reset_index(inplace=True)
    word_score_type_data.columns = ['score', 'scorecount']

    for i in range(10):
        if not ((i+1) in word_score_type_data['score'].tolist()):
            s = pd.Series({'score': (i+1), 'scorecount': 0})
            word_score_type_data = word_score_type_data.append(s, ignore_index=True)


    mpl.rcParams['font.sans-serif'] = ['SimHei']
    plt.bar(word_score_type_data['score'].tolist(), word_score_type_data['scorecount'].tolist(), alpha=0.5, width=0.3,
            color='yellow', edgecolor='red', label='The First Bar', lw=3)
    plt.xticks(np.arange(1, 11), ('1分', '2分', '3分', '4分', '5分',
                                  '6分', '7分', '8分', '9分', '10分'), rotation=30)
    plt.xlabel('图2. 评论评分分布', fontsize=10)

    pic_file = out_path + "/" + bookid + "_score.png"
    plt.savefig(pic_file)
    plt.show()


    s_x = word_score_data['score'].tolist()
    s_y = word_score_data['word_length'].tolist()
    T = np.arctan2(s_x, s_y)
    plt.scatter(s_x, s_y, c=T, s=25, alpha=0.4, marker='o')
    plt.xlabel('图3. 评论与评分散点图', fontsize=10)
    pic_file = out_path + "/" + bookid + "_scorescatter.png"
    plt.savefig(pic_file)
    plt.show()


    x_data = [str(x)+"分" for x in word_score_type_data['score'].tolist() ]
    y_data = word_score_type_data['scorecount'].tolist()
    pd_out_word = pd.DataFrame(data={'评分': x_data, '评论数量': y_data})
    all_comment = pd_out_word['评论数量'].sum()
    p_rate = [("%.2f" % (x * 100.0 / all_comment)) + "%" for x in pd_out_word['评论数量'].tolist()]
    pd_out_word['占比'] = p_rate

    table_file = out_path + "/" + bookid + "_score.csv"
    print(pd_out_word)
    pd_out_word.to_csv(table_file, index=None, encoding=WEB_SITE_CHARSETTING)


#针对评论用户的用户级别进行分析
def dobuyerlevelanalysis(df_data:pd.DataFrame, out_path, bookid):
    word_score_data = df_data.copy()
    word_score_data['word_length'] = word_score_data['comment'].str.len()
    word_score_data = word_score_data[['buyer', 'buyer_level', 'score', 'word_length']]
    buyer_level_type_data = (word_score_data['buyer_level'].value_counts()).to_frame(name="levelcount")
    buyer_level_type_data.reset_index(inplace=True)
    buyer_level_type_data.columns = ['level', 'levelcount']

    level_list = buyer_level_type_data['level'].tolist()
    level_y = buyer_level_type_data['levelcount'].tolist()
    show_list = ['钻石会员', '黄金会员', '白银会员', '普通会员']
    show_y = [0, 0, 0, 0]

    for i in range(len(level_list)):
        for j in range(len(show_list)):
            if level_list[i] == show_list[j]:
                show_y[j] = level_y[i]
                break
    mpl.rcParams['font.sans-serif'] = ['SimHei']
    plt.bar(show_list, show_y, alpha=0.5, width=0.3,
            color='yellow', edgecolor='red', label='The First Bar', lw=3)

    plt.xlabel('图4. 评论用户级别分布', fontsize=10)
    pic_file = out_path + "/" + bookid + "_buylevel.png"
    plt.savefig(pic_file)
    plt.show()


    pd_out_word = pd.DataFrame(data={'用户等级': show_list, '评论数量': show_y})
    all_comment = pd_out_word['评论数量'].sum()
    p_rate = [("%.2f" % (x * 100.0 / all_comment)) + "%" for x in pd_out_word['评论数量'].tolist()]
    pd_out_word['占比'] = p_rate

    table_file = out_path + "/" + bookid + "_buylevel.csv"
    print(pd_out_word)
    pd_out_word.to_csv(table_file, index=None, encoding=WEB_SITE_CHARSETTING)


if __name__ == '__main__':
    #获取运行环境目录
    dirname, filename = os.path.split(os.path.abspath(sys.argv[0]))
    url_file = dirname +"/"+IN_PATH+"/"+URL_FILENAME

    if not (os.path.isfile(url_file)):
        print("没有找到URL文件，处理结束！ url file (%s)" % (url_file))
        sys.exit(0)

    out_path = dirname +"/"+OUT_PATH
    if not (os.path.isdir(out_path)):
        os.makedirs(out_path)

    #获取图书URL地址
    book_url = ""
    with open(url_file, 'r') as furl:
        lines = furl.readline()
        if len(lines) > 0:
            book_url = str(lines).strip()

    if book_url == "":
        print("URL不合法，处理结束！")
        sys.exit(0)


    commentAnalysisTool = BookCommentWork()
    print("开始获取评论数据，URL(%s)" % (book_url))
    commentAnalysisTool.doLoadBookComments(book_url)

    commentAnalysisTool.save(out_path)
    print("开始获取评论数据结束!")

    #使用本地存储的数据进行分析，目前注释了，采用网上采集的数据进行分析
    # commentAnalysisTool.loadfromfile(OUT_PATH, "22879704")


    pddata = commentAnalysisTool.toPDData()
    if ((pddata is None) or (len(pddata) == 0)):
        print("没有要分析的数据！退出！")
        sys.exit(0)


    #对数据进行分析
    #评论字数分析
    dowordlenanalysis(pddata, OUT_PATH, commentAnalysisTool.getBook().getProductID())

    #图书评分与评论分析
    doscoreanalysis(pddata, OUT_PATH, commentAnalysisTool.getBook().getProductID())

    # 用户级别与评论分析
    dobuyerlevelanalysis(pddata, OUT_PATH, commentAnalysisTool.getBook().getProductID())

    #评论关键词分析
    judgework = Wordjudge()
    judgework.genKeyWord(pddata['comment'].tolist(), topK=100)
    judgework.showWordCloud(IN_PATH, OUT_PATH, commentAnalysisTool.getBook().getProductID())

    keyword, weight = judgework.getallKeyWord()
    key_list = []
    for i in range(len(keyword)):
        key_list.append([keyword[i], weight[i]])
        print("评论关键词 %s (权重 %s)" % (keyword[i], weight[i]))
    pd_keydata = pd.DataFrame(data=key_list, columns=['关键词', '权重'])
    pd_keydata.to_csv(OUT_PATH+"/"+commentAnalysisTool.getBook().getProductID()+"_keyword.csv",
                      index=None, encoding=WEB_SITE_CHARSETTING)

    # 虚假评论含量检测
    bad_list, resultdata = judgework.doCalCommentBadRate(pddata['comment'].tolist(),
                                                         keywordRate=0.02, keywordinComment=1)
    print(("虚假评论占比:%.2f" % (len(bad_list)*100.0/len(resultdata)))+"%")

    #保存虚假评论文件
    bad_comment_textfile = OUT_PATH+"/"+commentAnalysisTool.getBook().getProductID()+"_badcomment.txt"
    f1 = open(bad_comment_textfile, 'w')
    for bad in bad_list:
        f1.writelines(bad + "\n")
    f1.close()

    print("检测完成！")
