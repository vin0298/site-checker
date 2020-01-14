#!/bin/env/python3

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
		self.crawled_urls = set([])
		self.tried_urls = set([])
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

	def simplify_url(self, url):
		if not url.startswith('/') and not url.startswith('http://') and not url.startswith('https://'):
			url = '/' + url
		url = url.replace("www.", "")
		url = url.replace("https://", "http://")
		return url

	# Replace wwww
	def parse_links(self, html, parent_url):
		try:
			soup = BeautifulSoup(html, "html.parser")
			links = soup.find_all("a", href=True)

			for link in links:
				url = link['href']
				#print("Getting link %s" % url)
				if url.startswith('tel:') or url.startswith('mailto:') or url.startswith('#'): continue
				url = urljoin(parent_url, url)
				if not self.robot_txt_helper.can_fetch('*', url): continue
				formatted_url = self.simplify_url(url)
				if formatted_url.startswith('/') or formatted_url.startswith(self.root_url):
					formatted_url = urljoin(self.root_url, formatted_url)
					self.tried_urls.add(formatted_url)
					if formatted_url not in self.processed_urls:
						self.urls_to_crawl.put(formatted_url)
						self.crawled_urls.add(formatted_url)
				elif self.check_if_url_is_target(formatted_url):
					print("External URL detected: %s" % url)
					print("Found from parent: %s" % parent_url)
					self.external_urls.setdefault(parent_url, set([])).add(url)
				else:
					self.non_target_external_links.setdefault(parent_url, set([])).add(url)
		except Exception as e:
			print("====> Exception when parsing links %s" % e)
			print("====> Exception when parsing the link %s" % parent_url)
			return

	def parse_image_links(self, html, parent_url):
		soup = BeautifulSoup(html, "html.parser")
		img_links = soup.find_all("img")
		for img_link in img_links:
			img_url = img_link.get('src')
			if img_url is None: continue

			formatted_url = self.simplify_url(img_url)
			if not self.robot_txt_helper.can_fetch('*', formatted_url): continue
			if img_url in self.processed_urls: continue
			if self.check_if_url_is_target(formatted_url):
				print("External img URL detected: %s" % img_url)
				print("Found from parent: %s" % parent_url)
				self.external_urls.setdefault(parent_url, set([])).add(img_url)
			elif not (formatted_url.startswith(self.root_url) or formatted_url.startswith('/')):
				self.non_target_external_links.setdefault(parent_url, set([])).add(img_url)
			self.processed_urls.add(img_url)

	def post_scrape_callback(self, res):
		result = res.result()
		if result and result.status_code == 200:
			self.parse_links(result.text, result.url)
			self.parse_image_links(result.text, result.url)
			print("Finished processing %s" % result.url)

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
		filename = time.ctime().replace(" ", "_") + "_external_links.html"
		print("Writing all external links found to a file named: % s" % filename)
		try:
			with open(filename, "w+") as file:
				for parent_link, links in self.external_urls.items():
					href_tag = '<a href="' + parent_link + '">' + parent_link + '</a>'
					header = '<p><strong>External links linked from: ' + href_tag + '</strong></p>\n'
					# header = "<p><strong>>External links linked from: " + parent_link + "</strong></p>\n"
					file.write(header)
					for link in links:
						link_tag = '<a href="' + link + '">' + link + '</a>'
						content = "<p>------> " + link_tag + "</p>\n"
						print(content)
						file.write(content)
				print("Finished writing the external_links")
		except Exception as e:
			print("An exception has occured: \n %s" % e)

	# TODO: Group broken links based on their errors? 404s or Timeouts to make it more descriptive
	# This might be empty if the user retries for broken links
	def print_all_broken_links(self):
		filename = time.ctime().replace(" ", "_") + "_broken_links.html"
		print("Writing all broken links found to a file named: % s" % filename)
		try:
			with open(filename, "w+") as file:
				file.write("<p><strong>Broken links found: </strong></p>")
				for link in self.broken_links:
					link_tag = '<a href="' + link + '">' + link + '</a>'
					file.write("<p>" + link_tag + "</p>\n")
			print("Finished writing the broken_links")
		except Exception as e:
			print("An exception has occured: \n %s" % e)

	def print_all_crawled_links(self):
		filename = time.ctime().replace(" ", "_") + "_crawled_links.html"
		print("Writing all crawled links found to a file named: % s" % filename)
		try:
			with open(filename, "w+") as file:
				file.write("<p><strong>Crawled links: </strong></p>")
				for link in self.crawled_urls:
					link_tag = '<a href="' + link + '">' + link + '</a>'
					file.write("<p>" + link_tag + "</p>\n")
				file.write("<p><strong>Tried links: </strong></p>")
				for link in self.tried_urls:
					link_tag = '<a href="' + link + '">' + link + '</a>'
					file.write("<p>" + link_tag + "</p>\n")
			print("Finished writing the crawl_links")
		except Exception as e:
			print("An exception has occured: \n %s" % e)		

	def write_all_non_target_external_links(self):
		filename = time.ctime().replace(" ", "_") + "_non_target_external.html"
		print("Writing all non-target external URLs found to a file named: % s" % filename)
		try:
			with open(filename, "w+") as file:
				for parent_link in list(self.non_target_external_links):
					href_tag = '<a href="' + parent_link + '">' + parent_link + '</a>'
					header = '<p><strong>External links linked from: ' + href_tag + '</strong></p>\n'
					file.write(header)
					for link in self.non_target_external_links[parent_link]:
						link_tag = '<a href="' + link + '">' + link + '</a>'
						content = "<p>------> " + link_tag + "</p>\n"
						print(content)
						file.write(content)
				print("Finished writing non_target_external_links")
		except Exception as e:
			print("An exception has occured: \n %s" % e)

	def reprocess_broken_links(self):
		for broken_link in self.broken_links:
			self.processed_urls.remove(broken_link)
			self.urls_to_crawl.put(broken_link)
		self.broken_links = set([])

	# Retry broken links
	# TODO: Check the retry broken links feature
	def run_crawler(self):
		while True:
			try:
				target_url = self.urls_to_crawl.get(timeout=30)
				if target_url not in self.processed_urls:
					print("Processing the URL: %s" % target_url)
					self.processed_urls.add(target_url)
					job = self.pool.submit(self.parse_page, target_url)
					job.add_done_callback(self.post_scrape_callback)
			except Empty:
				print("Ran out of links to crawl!")
				# Might need to wait for all threads to finish executing
				response = input('\n--------> Retry broken links?: y/n  <------------\n')
				if response.lower() == 'y':
					# Remove broken_links from processed_urls
					print("Retrying broken links....")
					self.pool.submit(self.reprocess_broken_links)
					continue
				print("User refused to retry for broken links")
				self.pool.submit(self.print_all_external_links)
				self.pool.submit(self.print_all_broken_links)
				self.pool.submit(self.write_all_non_target_external_links)
				self.pool.submit(self.print_all_crawled_links)
				return
			except Exception as e:
				print("Exception occured with the following url: %s" % target_url)
				print(e)
				continue

if __name__ == '__main__':
	target_links_list = []
	start_URL = input("-----> Please enter the URL where you want to start crawling from: \n")
	response = input("------> Please enter URLs to check whether your website has a link to this website. If you wish to enter none, type in 'n'\n")
	while response.lower() != 'n':
		target_links_list.append(response)
		response = input("------> Please enter URLs to check whether your website has a link to this website. If you wish to enter no more, type in 'n'\n")

	crawler = ExternalLinkScraper(start_URL, target_links_list)
	crawler.run_crawler()
