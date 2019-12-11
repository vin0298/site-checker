#!/usr/bin/env python3

import sys
import time
from bs4 import BeautifulSoup
import requests 
import requests.exceptions
from urllib.parse import urlsplit
from urllib.parse import urlparse
from collections import deque
import urllib.robotparser as urlrobot

# Check if the url is considered "external" by the user
def check_if_url_is_target(url):
	if len(target_links) == 0: return True
	for target_external_url in target_links:
		if target_external_url in url: return True
	return False

# Try to retrieve the robots.txt
def obey_robots_protocol(url):
	if url.endswith('/'):
		robot_txt_path = url
	else:
		robot_txt_path = url + '/'

	if requests.head(robot_txt_path).status_code < 400:
		robot_parser = urlrobot.RobotFileParser()
		robot_parser.set_url(robot_txt_path)
		robot_parser.read()
		return robot_parser
	else:
		print("Could not retrieve robots.txt file. Please supply the base URL")
		exit()

# See if there is an argument passed in to the script
if len(sys.argv) < 2:
	print("Please add the base URL to crawl for as the first argument to recursively check for external links.\nAdd external hostnames to parse for argument")
	exit()

target_links = sys.argv[2:]
default_target = (len(target_links) == 0)

# Uncomment this after testing
start_URL = sys.argv[1]

robot_txt_parser = obey_robots_protocol(start_URL)

# Deque of links to crawl next
new_urls_to_crawl = deque([start_URL])

# Create sets to make sure the links that are being crawled are unique
# Set to keep track of links in the same domain
local_urls = set()

# Set to keep track of broken links
broken_links = set()

# Set to keep track of external links
external_links = set()

# Set to keep track of processed URLs
processed_urls = set()

# Keep on crawling until the deque is empty
while len(new_urls_to_crawl):
	url_to_crawl = new_urls_to_crawl.popleft()
	processed_urls.add(url_to_crawl)
	if robot_txt_parser.can_fetch('*', url_to_crawl):
		try:
			print("B4 request: %s" % url_to_crawl)
			response = requests.get(url_to_crawl, timeout=(10, 30))
		except(requests.exceptions.MissingSchema, requests.exceptions.ConnectionError, requests.exceptions.InvalidURL, 
				requests.exceptions.InvalidSchema) as e:
			print(e)
			broken_links.add(url_to_crawl)
			continue

		url_parts = urlsplit(url_to_crawl)
		base_url_to_crawl = "{0.scheme}://{0.netloc}".format(url_parts)
		crawled_domain = base_url_to_crawl.replace("www.", "")
		url_path = url_to_crawl[:url_to_crawl.rfind('/') + 1] if '/' in url_parts.path else url_to_crawl

		print("Proccessing %s" % url_to_crawl)
		soup = BeautifulSoup(response.text, "lxml")
		for link in soup.find_all("a"):    
			# extract link url from the anchor   
			#print("anchors found %s" % link)
			anchor = link.attrs["href"] if "href" in link.attrs else ''
			if anchor.startswith('/'):   
				# Relative URL -> local URL     
				local_link = base_url_to_crawl + anchor        
				local_urls.add(local_link)   
			elif check_if_url_is_target(anchor):  
				print("External link detected: %s" % anchor)      
				external_links.add(anchor) 
			elif crawled_domain in anchor:        
				local_urls.add(anchor)    
			elif not anchor.startswith('http'):        
				local_link = url_path + anchor        
				local_urls.add(local_link)    

			for i in local_urls:    
				if not i in new_urls_to_crawl and not i in processed_urls:        
					new_urls_to_crawl.append(i)
		print("finished processing %s" % url_to_crawl)
	else:
		print("Not allowed by robots.txt %s", url_to_crawl)
	# time.sleep(1)

print("External links found: ")
for link in external_links:
	print(link)

print("Broken links found: ")
for link in broken_links:
	print(link)






