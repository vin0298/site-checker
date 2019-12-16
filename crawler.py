#!/usr/bin/env python3

import sys
import time
from bs4 import BeautifulSoup
import requests 
import requests.exceptions
from urllib.parse import urlsplit, urlparse, urljoin
import urllib.robotparser as urlrobot
from datetime import datetime

from concurrent.futures import ThreadPoolExecutor
from queue import Queue, Empty

class ExternalLinkScraper:
	def __init__(self, base_url, target_links_list):
		self.base_url = base_url
		self.robot_txt_helper = self.obey_robots_protocol(base_url)
		self.root_url = "{0.scheme}://{0.netloc}".format(urlsplit(base_url)).replace("www.", "")
		self.pool = ThreadPoolExecutor(max_workers=30)
		self.processed_urls = set([])
		self.external_urls = {}
		self.urls_to_crawl = Queue()
		self.urls_to_crawl.put(base_url)
		self.broken_links = set([])
		self.target_links = target_links_list
		self.non_target_external_links = {}
		print("Root_url: %s" % self.root_url)

	def obey_robots_protocol(self, url):
		if url.endswith('/'):
			robot_txt_path = url
		else:
			robot_txt_path = url + '/'

		robot_txt_path = robot_txt_path + 'robots.txt'
		print("url for robots.txt %s " % robot_txt_path)

		if requests.head(robot_txt_path).status_code < 400:
			print("Robots.txt found! ")
			robot_parser = urlrobot.RobotFileParser()
			robot_parser.set_url(robot_txt_path)
			robot_parser.read()
			return robot_parser
		else:
			print("Could not retrieve robots.txt file. Please supply the base URL")
			exit()

	# Replace wwww
	def parse_links(self, html, parent_url):
		soup = BeautifulSoup(html, "html.parser")
		links = soup.find_all("a", href=True)
		for link in links:
			url = link['href']
			if not self.robot_txt_helper.can_fetch('*', url): continue
			if url.startswith('tel'): continue
			formatted_url = url.replace("www.", "")
			formatted_url = formatted_url.replace("https://", "http://")
			if url.startswith('/') or url.startswith('#') or url.startswith('?') or formatted_url.startswith(self.root_url):
				url = urljoin(self.root_url, url)
				if url not in self.processed_urls:
					self.urls_to_crawl.put(url)
			elif self.check_if_url_is_target(url):
				print("External URL detected: %s" % url)
				print("Found from parent: %s" % parent_url)
				self.external_urls.setdefault(parent_url, set([])).add(url)
			else:
				print("Non-target external URL detected: %s" % url)
				print("Found from parent: %s" % parent_url)
				self.non_target_external_links.setdefault(parent_url, set([])).add(url)

	def parse_image_links(self, html, parent_url):
		soup = BeautifulSoup(html, "html.parser")
		img_links = soup.find_all("img")
		for img_link in img_links:
			img_url = img_link['src']
			if not self.robot_txt_helper.can_fetch('*', img_url): continue
			if img_url.startswith('/') or img_url.startswith(self.root_url):
				img_url = urljoin(self.root_url, img_url)
				if img_url not in self.processed_urls:
					self.processed_urls.add(img_url)
			elif self.check_if_url_is_target(img_url):
				print("External img URL detected: %s" % img_url)
				print("Found from parent: %s" % parent_url)
				self.external_urls.setdefault(parent_url, set([])).add(img_url)
			else:
				self.non_target_external_links.setdefault(parent_url, set([])).add(img_url)

	def post_scrape_callback(self, res):
		result = res.result()
		if result and result.status_code == 200:
			self.parse_links(result.text, result.url)
			self.parse_image_links(result.text, result.url)

	# TODO: need parent_url for better information to th users
	def parse_page(self, url):
		try:
			res = requests.get(url, timeout=(10, 30))
			return res
		except requests.RequestException as req_err:
			print("something went wrong when requesting with url: %s" % url)
			print(req_err)
			self.broken_links.add(url)
			return 

	def check_if_url_is_target(self, url):
		if (len(self.target_links) == 0): return True
		strip_url = url.replace("www.", "")
		strip_url = url.replace("https://", "http://")
		for target_external_url in self.target_links:
			if target_external_url in strip_url: return True
		return False

	def print_all_external_links(self):
		print("Writing all external links found to a file named: external_links.txt")
		try:
			with open("external_links.txt", "w+") as file:
				for parent_link, links in self.external_urls.items():
					header = "External links linked from: " + parent_link + "\n"
					file.write(header)
					for link in links:
						content = "------> " + link + "\n"
						print(content)
						file.write(content)
				print("Finished writing the external_links")
		except Exception as e:
			print("An exception has occured: \n %s" % e)

	# TODO: Group broken links based on their errors? 404s or Timeouts to make it more descriptive
	def print_all_broken_links(self):
		print("Writing all broken links found to a file named: broken_links.txt ")
		try:
			with open("broken_links.txt", "w+") as file:
				for link in self.broken_links:
					file.write(link + "\n")
			print("Finished writing the broken_links")
		except Exception as e:
			print("An exception has occured: \n %s" % e)

	def write_all_non_target_external_links(self):
		print("Writing all non-target external URLs found to a file named: non_target_external.txt")
		try:
			with open("non_target_external.txt", "w+") as file:
				for parent_link, links in self.non_target_external_links.items():
					header = "Non-target external links linked from: " + parent_link + "\n"
					file.write(header)
					for link in links:
						content = "------> " + link + "\n"
						print(content)
						file.write(content)
				print("Finished writing non_target_external_links")
		except Exception as e:
			print("An exception has occured: \n %s" % e)

	def run_crawler(self):
		while True:
			try:
				target_url = self.urls_to_crawl.get(timeout=60)
				if target_url not in self.processed_urls:
					print("Processing the URL: %s" % target_url)
					self.processed_urls.add(target_url)
					job = self.pool.submit(self.parse_page, target_url)
					job.add_done_callback(self.post_scrape_callback)
			except Empty:
				print("Ran out of links to crawl!")
				self.pool.submit(self.print_all_external_links)
				self.pool.submit(self.print_all_broken_links)
				self.pool.submit(self.write_all_non_target_external_links)
				return
			except Exception as e:
				print("Exception occured with the following url: %s" % target_url)
				print(e)
				continue


# See if there is an argument passed in to the script

if __name__ == '__main__':
	if len(sys.argv) < 2:
		print("Please add the base URL to crawl for as the first argument to recursively check for external links.\nAdd external hostnames to parse for argument")
		exit()

	start_URL = sys.argv[1]
	target_links_list = sys.argv[2:]
	crawler = ExternalLinkScraper(start_URL, target_links_list)
	crawler.run_crawler()
