#!/usr/bin/env python
# _*_coding=utf8 _*_
'''
Crawl the online_time of zhihu user,
Need the user name and password
store the data in the mysql
'''

import requests
import cookielib
import MySQLdb
import _mysql_exceptions
import time
import re
from bs4 import BeautifulSoup


class DoubanSpider(object):
    
    domain = 'http://www.douban.com'
    def __init__(self, login, password):
        self.login = login
        self.password = password
        self.login_url = 'http://www.douban.com/accounts/login'
        
        self.jar = cookielib.CookieJar()
        self.pwd = {
            'form_email':self.login,
            'form_password':self.password,
            'source':None,
            'remember':'on',
            'login':'登录',
        }
        self.header = {
            'User-agent':'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.9; rv:32.0) Gecko/20100101 Firefox/32.0',
            '(Request-Line)':'POST /group/topic/62688349/add_comment HTTP/1.1',
            'Host':'www.douban.com',
            'Accept-Language':'zh-cn,zh;q=0.8,en-us;q=0.5,en;q=0.3',
            'Connetcting':'keep-alive'
        }
        self.session = requests.Session()
        self.response = self.session.get(self.login_url, cookies=self.jar)
        
    def login_douban(self, redir=domain):
        '''
        after login, jump to redir_url
        then can use response
        '''
        
        self.pwd['redir'] = redir
        self.response = self.session.post(self.login_url, headers=self.header, cookies=self.response.cookies, data=self.pwd)
        print("Posted pwd....")
        
        #for captcha code
        while True:
            soup = BeautifulSoup(self.response.text)
            self.captcha = soup.find('img', class_="captcha_image")
            if self.captcha:
                self.captcha_handle()
            else:
                break
            
    def captcha_handle(self):
        '''
        take the self.captcha, a soup object
        open the captcha image with web browser,
        and post the capture to website.
        '''
        import webbrowser
        captcha_url = self.captcha.attrs['src']
        captcha_id = re.findall('id=(.+)&', captcha_url)[0]
        webbrowser.open(captcha_url)
        captcha_solution = raw_input("please input captcha code: ")
        self.pwd['captcha-id'] = captcha_id
        self.pwd['captcha-solution'] = captcha_solution
        
        self.response = self.session.post(self.login_url, data=self.pwd)
        
        
    def crawl_comments(self, topic_url):
        '''
        crawl the comments of the topic,
        store in mysql with style of 
        user name, comment content, reply_url
        '''
        db = MySQLdb.connect(host="localhost", port=3307, user='root', passwd='passwd', db='douban')
        cursor = db.cursor()
        cursor.execute('alter table comments auto_increment=1')
        db.commit()
        comment_res = self.session.get(topic_url)
        
        #crawl all pages's url
        soup = BeautifulSoup(comment_res.text)
        all_pages_urls = [topic_url]
        nextpage = soup.find('span', class_="thispage")
        while True:
            nextpage = nextpage.next_sibling.next_sibling
            #there is '\n' between two page object            
            try:
                all_pages_urls.append(nextpage.attrs['href'])
            except(KeyError):
                break
        print("total %s pages" %len(all_pages_urls))
        
        for each_url in all_pages_urls:
            response = self.session.get(each_url)
            soup = BeautifulSoup(response.text)
            
            #crawl each comment region
            regions = soup.find_all('li', class_="clearfix comment-item")
            for region in regions:
                user_name = region.find('h4').find('a').text
                comment = region.find('p').text
                reply_url = region.find('a', class_="lnk-reply").attrs['href']
                
                sql = 'insert into comments (user_name, comment, reply_url) values ("%s","%s","%s")'\
                    %(user_name.encode('utf8'), comment.encode('utf8'), reply_url)
                try:
                    cursor.execute(sql)
                except(_mysql_exceptions.DataError):
                    print("comment too long, pass")
                    pass
            
        db.commit()
        cursor.close()
        db.close()
        print("comment crawled succeed.")           
        
    def post_comment(self, comment, ID=1):
        '''
        reply to the comment.
        ID is the ID of comments table, is the serial number of the comments
        ''' 
        db = MySQLdb.connect(host="localhost", port=3307, user='root', passwd='passwd', db='douban')
        cursor = db.cursor()
        
        cursor.execute('select reply_url from comments where ID=%d' %ID)
        reply_url = cursor.fetchone()[0]
     
        cursor.close()
        db.close()
        print("ID: %s, reply_url: %s" %(ID, reply_url))
        
        #get reply cid, the signal of user name
        ref_cid = re.findall('cid=(\d+)#', reply_url)[0]
        print ref_cid
        topic_url = re.findall('(.+)\?cid', reply_url)[0]
        post_url = topic_url + "add_comment"
        post_data = {
            'ref_cid':ref_cid,
            'rv_comment':comment,
            'submit_btn':'加上去',
        }
        
        #login
        self.login_douban()
        #import pdb; pdb.set_trace()
        self.response = self.session.get(reply_url)        
        soup = BeautifulSoup(self.response.text)
        #test if login is successful
        login = soup.find_all('li', class_="nav-user-account")
        
        #import pdb; pdb.set_trace()    
        #find ck from cookies
        cookies_dict = requests.utils.dict_from_cookiejar(self.session.cookies)
        post_data['ck'] = cookies_dict['ck']
        #print cookies_dict['ck']
        
        self.response = self.session.get(reply_url)        
        soup = BeautifulSoup(self.response.text)
        #test if login is successful
        #login = soup.find_all('li', class_="nav-user-account")
        #print login
        
        #find start from the html
        try:
            start = soup.find('input', id='start').attrs['value']
        except(IndexError, AttributeError, TypeError):
            start = '1000'
            import pdb; pdb.set_trace()
        post_data['start'] = start
        print("post_data: %s" %post_data)
        #import pdb; pdb.set_trace()
        
        self.response = self.session.post(post_url, data=post_data)
        
        #check if comment succeed
        post_ok_url = topic_url + '?start=' + start +'&post=ok'
        self.response = self.session.get(post_ok_url)
        soup = BeautifulSoup(self.response.text)
        regions = soup.find_all('li', class_="clearfix comment-item")
        for region in regions:
            if region.find_all(re.compile('youiskk')):
                print region
                return
        import pdb; pdb.set_trace()
        
    

def test_crawl_comments():
    spider = DoubanSpider('user', 'password')
    spider.crawl_comments('http://www.douban.com/group/topic/63187199/?start=0')  
    
def test_post_comment():
    spider = DoubanSpider('user', 'password')
    spider.post_comment('这是一个测试，不必理会。')
        
if __name__ == '__main__':
    #test_crawl_comments()
    test_post_comment()
    
