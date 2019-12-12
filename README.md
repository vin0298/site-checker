## Python Project  
A simple web crawler that looks for external URLs of a website.  
This program takes at least 1 arguments:  
- The first argument is the base_URL for the crawler to start crawling. It must
be the base to ensure it is able to access robots.txt file and obey it.  
- Optional arguments would be the URLs that you want the crawler to look out for
as external links.    
This program will write two files: "external_links.txt" to store all the
external URLs it found and "broken_links.txt" which is to store all the
unreachable URLs when it is crawling.    
Future Implementation:  
- Retry for broken links  
- More freedom to name the files  
- Ask for input instead of providing arguments  

