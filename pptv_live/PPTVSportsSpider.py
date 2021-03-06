# -*- coding: utf-8 -*-

import urllib2
from random import random
from django.db import connection
from BeautifulSoup import BeautifulSoup
from sportsModel import sportsModel
from datetime import datetime
import re
import json
import os 
import logging

logger = logging.getLogger('appserver')

ROOT = "/mnt/m3u8/"
cursor = connection.cursor()
#ORIGINAL HTML RESPONSE
date = datetime.now().strftime("%Y-%m-%d")

class PPTVSpider(object):

	def __init__(self, cursor):
		super(PPTVSpider, self).__init__()
		self.cursor=cursor

	def getBroadList(self, date):
		req = urllib2.Request("http://live.pptv.com/api/subject_list?cb=load.cbs.cbcb_4&date="+date+"&type=35&tid=&cid=&offset=0", headers={
			"user-agent": "Mozilla/5.0 (iPad; CPU OS 8_1 like Mac OS X) AppleWebKit/600.1.4 (KHTML, like Gecko) Version/8.0 Mobile/12B410 Safari/600.1.4",
			})
		try:
			webpage = urllib2.urlopen(req)
		except Exception, e:
			logger.error(e)
			logger.error("601 request fail in html page request")
		pageContent = webpage.read()
		
		#ORIGINAL URL LIST
		#href=\"http:\/\/v.pptv.com\/show\/Sv5GxS2TA0GkIoo.html
		regex = r"http:\\\/\\\/v.pptv\.com\\\/show\\\/[A-Za-z0-9]*\.html"
		pattern = re.compile(regex)
		matchGroup = pattern.findall(pageContent)

		urlNum = len(matchGroup)
		urlGroup = []
		for index in range(0, urlNum):
			urlGroup.append(matchGroup[index].replace("\\", ""))
		return urlGroup

	def firstStepAnalyser(self, urlGroup):
		firstStepUrlList = []
		for url in urlGroup:
			req = urllib2.Request(url, headers={
			"user-agent": "Mozilla/5.0 (iPad; CPU OS 8_1 like Mac OS X) AppleWebKit/600.1.4 (KHTML, like Gecko) Version/8.0 Mobile/12B410 Safari/600.1.4",
			})
			try:
				webpage = urllib2.urlopen(req)
			except Exception, e:
				logger.error(e)
				logger.error("602 request fail in first step request")
				continue
			pageContent = webpage.read()
			pageContent=pageContent.replace(" ", "").replace("\t", "").replace("\n", "")
			regex = r"<scripttype=\"text/javascript\">varwebcfg={.*};</script>"
			pattern = re.compile(regex)
			matcher = pattern.search(pageContent)
			if matcher:
				try:
					webcfg = matcher.group().replace(" ", "").replace("\t", "").replace("\n", "")
					idPattern = re.compile(r"\"id\":[0-9]*")
					idValue = idPattern.search(webcfg).group()
					idValue = idValue.split(":")[1]
					kkPattern = re.compile(r"\"ctx\":\"[A-Za-z0-9%]*%3D[A-Za-z0-9-]*\"")
					kkValue = kkPattern.search(webcfg).group()
					kkValueGroup=kkValue.split("3D")
					kkValue = kkValueGroup[len(kkValueGroup)-1].strip("\"")
					currentUrl = "http://web-play.pptv.com/webplay3-0-"+idValue+".xml?version=4&type=m3u8.web.pad&kk="+kkValue+"&o=v.pptv.com&rcc_id=0&cb=getPlayEncode"
					firstStepUrlList.append(currentUrl)
				except Exception, e:
					logger.error(e)
					logger.error("702 error in first analyse step")
					continue
			else:
				logger.error("701 error in match strp")
				continue
		return firstStepUrlList

	def secondStepAnalyser(self, firstStepUrlList):
		secondStepUrlList = []
		for url in firstStepUrlList:
			req = urllib2.Request(url, headers={
			"user-agent": "Mozilla/5.0 (iPad; CPU OS 8_1 like Mac OS X) AppleWebKit/600.1.4 (KHTML, like Gecko) Version/8.0 Mobile/12B410 Safari/600.1.4",
			})
			try:
				webpage = urllib2.urlopen(req)
			except Exception, e:
				logger.error(e)
				logger.error("603 request fail in second step request")
				break
			pageContent = webpage.read()
			pageContent=pageContent.replace("getPlayEncode(", "").rstrip(";()")
			fp = open("context.txt", "w")
			fp.write(pageContent)
			try:
				pageJson = json.loads(pageContent)
				# rid in 0,1,2,3
				rid = pageJson["childNodes"][0]["childNodes"][0]["childNodes"][1]["rid"].replace(".mp4", "")
				name = pageJson["childNodes"][0]["nm"]
				# port, segment in 3,5,7,9
				port = pageJson["childNodes"][5]["childNodes"][0]["childNodes"][0]
				#segment = pageJson["childNodes"][CHANGE THIS]["childNodes"][5]["childNodes"][0]
				segment = pageJson["childNodes"][5]["childNodes"][5]["childNodes"][0]
				currentUrl = "http://"+port+"/"+rid+".m3u8?type=m3u8.web.pad&k="+segment
				currentInfo = {"name":name, "url":currentUrl, "port":port}
				secondStepUrlList.append(currentInfo)
			except Exception, e:
				logger.error(e)
				logger.error("703 error in second analyse step")
				continue
		return secondStepUrlList

	def runSpider(self, date):

		logger.debug("PPTV Video Spider initialized...")
		urlGroup = self.getBroadList(date)
		logger.debug("There are "+ str(len(urlGroup)) + " videos today, start analysing.")
		firstStepUrlList = self.firstStepAnalyser(urlGroup)
		logger.debug(str(len(firstStepUrlList)) + "/" + str(len(urlGroup)) + " first step urls has been successfully fetched, start analysing.")
		secondStepUrlList = self.secondStepAnalyser(firstStepUrlList)
		logger.debug(str(len(secondStepUrlList)) + "/" + str(len(firstStepUrlList)) + " second step urls has been successfully fetched, start downloading.")

		logger.debug("start downloading m3u8 profiles...")
		successCount = 0
		for urlInfo in secondStepUrlList:
			successTs = 0
			currentUrl = urlInfo ["url"]
			currentPort = urlInfo ["port"].replace("\n", "")
			currentName = unicode(urlInfo ["name"]).encode("utf-8")
			vid = sportsModel().add_item("testName" , "sports", date)
			logger.debug("downloading: "+ currentUrl)
			req = urllib2.Request(currentUrl , headers={
			"user-agent": "Mozilla/5.0 (iPad; CPU OS 8_1 like Mac OS X) AppleWebKit/600.1.4 (KHTML, like Gecko) Version/8.0 Mobile/12B410 Safari/600.1.4",
			})
			try:
				m3u8page = urllib2.urlopen(req)
			except Exception, e:
				logger.error(e)
				logger.error("604 request fail in m3u8 request")
				continue
			m3u8Content = m3u8page.read()
			replacePattern = re.compile(r"\/[A-Za-z0-9]*\.ts\?start=[0-9]*&")
			matchList = replacePattern.findall(m3u8Content)
			for matchItem in matchList:
				m3u8Content = m3u8Content.replace(matchItem, "http://"+currentPort+matchItem)
			fp = open(ROOT+"m3u8/"+date+"-"+str(vid)+".m3u", "w")
			fp.write(m3u8Content)
			fp.close()
			urlPattern = re.compile(r"http:\/\/[0-9\.]*\/[A-Za-z0-9]*\.ts\?start=[0-9]*&during=[0-9]*&type=m3u8.web.pad&k=[A-Za-z0-9-]*&segment=[A-Za-z0-9_]*")
			urlList = urlPattern.findall(m3u8Content)
			for urlItem in urlList:
				logger.debug("downloading:" + urlItem)
				featurePattern = re.compile(r"start=[0-9]*&during=[0-9]*")
				match = featurePattern.search(urlItem)
				if match:
					currentFeature = match.group()
				else:
					currentFeature = "errorX="+str(successTs)
				req = urllib2.Request(urlItem, headers={
					"user-agent": "Mozilla/5.0 (iPad; CPU OS 8_1 like Mac OS X) AppleWebKit/600.1.4 (KHTML, like Gecko) Version/8.0 Mobile/12B410 Safari/600.1.4",
					})
				try:
					tsPage = urllib2.urlopen(req)
				except Exception, e:
					logger.error(e)
					logger.error("605 request fail in ts request")
					continue
				tsContent = tsPage.read()
				fp = open(ROOT+"ts/"+date+"-"+str(vid)+"-"+currentFeature+".ts", "w")
				fp.write(tsContent)
				fp.close()
				startPattern = re.compile(r'[0-9]*')
				matcher = startPattern.search(currentFeature)
				if matcher:
					start = matcher.group()
				else:
					start = "0"
				newUrl = "http://*********/pptvlive/readts"+str(vid)+str(start)+".ts?date="+date+"&vid="+str(vid)+"&"+currentFeature
				m3u8Content = m3u8Content.replace(urlItem, newUrl)
				successTs += 1
			logger.debug("Download finished, "+str(successTs)+"/"+str(len(urlList))+" ts files are downloaded successfully.")
			fp = open(ROOT+"m3u8New/"+date+"-"+str(vid)+".m3u", "w") 
			fp.write(m3u8Content)
			fp.close()
			successCount += 1
		logger.debug("Congratulations, download finished, "+str(successCount)+"/"+str(len(secondStepUrlList))+" is downloaded successfully.")
		logger.debug("Spider ceased.")
		return {"state":True, "info":str(successCount)+"/"+str(len(secondStepUrlList))+"succeeded"}
	
	def getPrecastList(self, date):
		#@date : it must be late than today
		req = urllib2.Request("http://live.pptv.com/api/subject_list?cb=load.cbs.cbcb_4&date="+date+"&type=35&tid=&cid=&offset=0", headers={
			"user-agent": "Mozilla/5.0 (iPad; CPU OS 8_1 like Mac OS X) AppleWebKit/600.1.4 (KHTML, like Gecko) Version/8.0 Mobile/12B410 Safari/600.1.4",
			})
		try:
			webpage = urllib2.urlopen(req)
		except Exception, e:
			logger.error(e)
			logger.error("601 request fail in html page request")
			return 
		pageContent = webpage.read().replace("\/", "/").replace("\\\"", "\"")

		soup = BeautifulSoup(pageContent)
		table = soup.find('table')
		trList = table.findAll("tr")
		infoList = []
		for item in trList:
			currentInfo = {}
			tdList = item.findAll("td")
			currentInfo["date"] = date
			currentInfo["starttime"] = tdList[0].text
			currentInfo["type"] = tdList[1].text
			currentInfo["name"] = tdList[2].find("div").contents[0].replace("\\n", "")
			infoList.append(currentInfo)
		return infoList

