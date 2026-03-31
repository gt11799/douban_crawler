#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Crawl Douban group comments and optionally reply to one comment.

This version uses SQLite instead of MySQL for easier local setup.
"""

import re
import sqlite3
import time
from http import cookiejar

import requests
from bs4 import BeautifulSoup


class DoubanSpider(object):
    domain = "https://www.douban.com"
    db_path = "douban.sqlite3"

    def __init__(self, login, password):
        self.login = login
        self.password = password
        # Douban moved to accounts/passport login entry.
        self.login_url = "https://accounts.douban.com/passport/login"

        self.jar = cookiejar.CookieJar()
        self.pwd = {
            "form_email": self.login,
            "form_password": self.password,
            "source": None,
            "remember": "on",
            "login": "登录",
        }
        self.header = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.9; rv:32.0) Gecko/20100101 Firefox/32.0",
            "Host": "www.douban.com",
            "Accept-Language": "zh-cn,zh;q=0.8,en-us;q=0.5,en;q=0.3",
            "Connection": "keep-alive",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        self.session = requests.Session()
        self.response = self.session.get(self.login_url, cookies=self.jar, headers=self.header)
        self._init_db()

    def _get_db(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._get_db() as db:
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS comments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_name TEXT NOT NULL,
                    comment TEXT NOT NULL,
                    reply_url TEXT NOT NULL
                )
                """
            )
            db.commit()

    def login_douban(self, redir=domain):
        """
        after login, jump to redir_url
        then can use response
        """

        self.pwd["redir"] = redir
        self.response = self.session.post(self.login_url, headers=self.header, data=self.pwd)
        print("Posted pwd....")

        # for captcha code
        while True:
            soup = BeautifulSoup(self.response.text, "html.parser")
            self.captcha = soup.find("img", class_="captcha_image")
            if self.captcha:
                self.captcha_handle()
            else:
                break

    def captcha_handle(self):
        """
        take the self.captcha, a soup object
        open the captcha image with web browser,
        and post the capture to website.
        """
        import webbrowser

        captcha_url = self.captcha.attrs["src"]
        captcha_id = re.findall("id=(.+)&", captcha_url)[0]
        webbrowser.open(captcha_url)
        captcha_solution = input("please input captcha code: ")
        self.pwd["captcha-id"] = captcha_id
        self.pwd["captcha-solution"] = captcha_solution

        self.response = self.session.post(self.login_url, data=self.pwd)

    def crawl_comments(self, topic_url):
        """
        crawl the comments of the topic,
        store in sqlite with style of
        user name, comment content, reply_url
        """
        with self._get_db() as db:
            db.execute("DELETE FROM comments")
            db.execute("DELETE FROM sqlite_sequence WHERE name='comments'")
            db.commit()

            comment_res = self.session.get(topic_url)

            # crawl all pages's url
            soup = BeautifulSoup(comment_res.text, "html.parser")
            all_pages_urls = [topic_url]
            nextpage = soup.find("span", class_="thispage")
            while nextpage:
                try:
                    nextpage = nextpage.next_sibling.next_sibling
                    all_pages_urls.append(nextpage.attrs["href"])
                except (KeyError, AttributeError):
                    break

            print("total %s pages" % len(all_pages_urls))

            for each_url in all_pages_urls:
                response = self.session.get(each_url)
                soup = BeautifulSoup(response.text, "html.parser")

                # crawl each comment region
                regions = soup.find_all("li", class_="clearfix comment-item")
                for region in regions:
                    user_name = region.find("h4").find("a").text.strip()
                    comment = region.find("p").text.strip()
                    reply_url = region.find("a", class_="lnk-reply").attrs["href"]

                    sql = "INSERT INTO comments (user_name, comment, reply_url) VALUES (?, ?, ?)"
                    try:
                        db.execute(sql, (user_name, comment, reply_url))
                    except sqlite3.DataError:
                        print("comment too long, pass")

            db.commit()
            print("comment crawled succeed.")

    def post_comment(self, comment, comment_id=17):
        """
        reply to the comment.
        comment_id is the ID of comments table, is the serial number of the comments
        """
        self.post_header = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.9; rv:32.0) Gecko/20100101 Firefox/32.0",
            "Host": "www.douban.com",
            "Accept-Language": "zh-cn,zh;q=0.8,en-us;q=0.5,en;q=0.3",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        with self._get_db() as db:
            cursor = db.execute("SELECT reply_url FROM comments WHERE id=?", (comment_id,))
            row = cursor.fetchone()

        if not row:
            raise ValueError("No comment found in sqlite db for id=%s" % comment_id)
        reply_url = row[0]
        print("ID: %s, reply_url: %s" % (comment_id, reply_url))

        # get reply cid, the signal of user name
        ref_cid = re.findall(r"cid=(\d+)#", reply_url)[0]
        topic_url = re.findall(r"(.+)\?cid", reply_url)[0]
        post_url = topic_url + "add_comment"

        post_data = {
            "ref_cid": ref_cid,
            "rv_comment": comment,
            "submit_btn": "加上去",
        }

        # login
        self.login_douban()
        self.response = self.session.get(reply_url, headers=self.header)

        # find ck from cookies
        cookies_dict = requests.utils.dict_from_cookiejar(self.session.cookies)
        post_data["ck"] = cookies_dict["ck"][1:5]

        # get the Content_Length
        content_length = str(87 + 3 * len(comment))
        self.post_header["Content-Length"] = content_length
        print(self.post_header)

        self.response = self.session.get(reply_url, headers=self.post_header)
        soup = BeautifulSoup(self.response.text, "html.parser")

        # find start from the html
        start_input = soup.find("input", id="start")
        start = start_input.attrs.get("value", "1000") if start_input else "1000"
        post_data["start"] = start
        print("post_data: %s" % post_data)

        referer_url = re.findall(r"(.+)#last", reply_url)
        if referer_url:
            self.post_header["Referer"] = referer_url[0]

        # response often takes a long time.
        try:
            self.response = self.session.post(post_url, data=post_data, headers=self.header)
        except requests.exceptions.ConnectionError:
            return

        # check if comment succeed
        soup = BeautifulSoup(self.response.text, "html.parser")
        regions = soup.find_all("li", class_="clearfix comment-item")
        for region in regions:
            if region.find_all(re.compile("user")):
                print(region)
                return

        raise RuntimeError("post comment might have failed; expected comment list entry not found")


if __name__ == "__main__":
    print(
        "DoubanSpider module loaded. Instantiate DoubanSpider(login, password) and run crawl_comments(topic_url)."
    )
