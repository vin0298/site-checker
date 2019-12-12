#!/usr/bin/env python3

import sys
import time
from bs4 import BeautifulSoup
import requests 
import requests.exceptions
from urllib.parse import urlsplit, urlparse, urljoin
from collections import deque
import urllib.robotparser as urlrobot
from datetime import datetime

from concurrent.futures import ThreadPoolExecutor
from queue import Queue, Empty

class ExternalLinkScraper:
	def __init__(self, base_url, target_links_list):
		self.base_url = base_url
		self.robot_txt_helper = self.obey_robots_protocol(base_url)
		self.root_url = "{0.scheme}://{0.netloc}".format(urlsplit(base_url))
		self.pool = ThreadPoolExecutor(max_workers=30)
		self.processed_urls = set([])
		self.external_urls = {}
		self.urls_to_crawl = Queue()
		self.urls_to_crawl.put(base_url)
		self.broken_links = set([])
		self.target_links = target_links_list

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

	def parse_links(self, html, parent_url):
		soup = BeautifulSoup(html, "html.parser")
		links = soup.find_all("a", href=True)
		for link in links:
			url = link['href']
			#print("link found: %s" % url)
			if not self.robot_txt_helper.can_fetch('*', url): continue
			if url.startswith('/') or url.startswith(self.root_url):
				url = urljoin(self.root_url, url)
				if url not in self.processed_urls:
					self.urls_to_crawl.put(url)
			elif self.check_if_url_is_target(url):
				print("External URL detected: %s" % url)
				print("Found from parent: %s" % parent_url)
				self.external_urls.setdefault(parent_url, []).append(url)

	def post_scrape_callback(self, res):
		result = res.result()
		if result and result.status_code == 200:
			self.parse_links(result.text, result.url)

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
		for target_external_url in self.target_links:
			if target_external_url in strip_url: return True
		return False

	def print_all_external_links(self):
		print("Writing all external links found to a file named: external_links.txt")
		try:
			with open("external_links.txt", "w+") as file:
				print("GETTING EXTERNAL LINKS")
				for parent_link, links in self.external_urls.items():
					header = "External links linked from: " + parent_link + "\n"
					print(header)
					file.write(header)
					for link in links:
						content = "------> " + link + "\n"
						print(content)
						file.write(content)
		except Exception as e:
			print("An exception has occured: \n %s" % e)

	# TODO: Group broken links based on their errors? 404s or Timeouts to make it more descriptive
	def print_all_broken_links(self):
		print("Writing all broken links found to a file named: broken_links.txt ")
		try:
			with open("broken_links.txt", "w+") as file:
				for link in self.broken_links:
					file.write(link + "\n")
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


































# target_links = sys.argv[2:]
# default_target = (len(target_links) == 0)

# # Uncomment this after testing
# start_URL = sys.argv[1]

# robot_txt_parser = obey_robots_protocol(start_URL)

# # Deque of links to crawl next
# new_urls_to_crawl = deque([start_URL])

# # Create sets to make sure the links that are being crawled are unique
# # Set to keep track of links in the same domain
# local_urls = set()

# # Set to keep track of broken links
# broken_links = set()

# # Set to keep track of external links
# external_links = set()

# # Set to keep track of processed URLs
# processed_urls = set()

# Keep on crawling until the deque is empty
# while len(new_urls_to_crawl):
# 	url_to_crawl = new_urls_to_crawl.popleft()
# 	processed_urls.add(url_to_crawl)
# 	if robot_txt_parser.can_fetch('*', url_to_crawl):
# 		try:
# 			print("B4 request: %s" % url_to_crawl)
# 			response = requests.get(url_to_crawl, timeout=(10, 30))
# 		except(requests.exceptions.MissingSchema, requests.exceptions.ConnectionError, requests.exceptions.InvalidURL, 
# 				requests.exceptions.InvalidSchema) as e:
# 			print(e)
# 			broken_links.add(url_to_crawl)
# 			continue

# 		url_parts = urlsplit(url_to_crawl)
# 		base_url_to_crawl = "{0.scheme}://{0.netloc}".format(url_parts)
# 		crawled_domain = base_url_to_crawl.replace("www.", "")
# 		url_path = url_to_crawl[:url_to_crawl.rfind('/') + 1] if '/' in url_parts.path else url_to_crawl

# 		print("Proccessing %s" % url_to_crawl)
# 		soup = BeautifulSoup(response.text, "lxml")
# 		for link in soup.find_all("a"):    
# 			# extract link url from the anchor   
# 			#print("anchors found %s" % link)
# 			anchor = link.attrs["href"] if "href" in link.attrs else ''
# 			if anchor.startswith('/'):   
# 				# Relative URL -> local URL     
# 				local_link = base_url_to_crawl + anchor        
# 				local_urls.add(local_link)   
# 			elif check_if_url_is_target(anchor):  
# 				print("External link detected: %s" % anchor)      
# 				external_links.add(anchor) 
# 			elif crawled_domain in anchor:        
# 				local_urls.add(anchor)    
# 			elif not anchor.startswith('http'):        
# 				local_link = url_path + anchor        
# 				local_urls.add(local_link)    

# 			for i in local_urls:    
# 				if not i in new_urls_to_crawl and not i in processed_urls:        
# 					new_urls_to_crawl.append(i)
# 		print("finished processing %s" % url_to_crawl)
# 	else:
# 		print("Not allowed by robots.txt %s", url_to_crawl)
# 	# time.sleep(1)

# print("External links found: ")
# for link in external_links:
# 	print(link)

# print("Broken links found: ")
# for link in broken_links:
# 	print(link)
