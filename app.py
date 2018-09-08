#!/bin/env python
# coding: utf-8
import sys
sys.path.append('./vendor')

import os
import re
import json
import requests
from flask import Flask, render_template, request, abort, jsonify
from urllib.parse import urlparse
from pymongo import MongoClient
from datetime import datetime, timezone, timedelta

import urllib.request

from linebot import (
	LineBotApi, WebhookHandler
)
from linebot.exceptions import (
	InvalidSignatureError
)
from linebot.models import (
	MessageEvent, TextMessage, TextSendMessage, StickerSendMessage, ImageSendMessage, BeaconEvent
)

app = Flask(__name__)

MONGO_URL = os.environ.get('MONGODB_URI')

if MONGO_URL:
	con = MongoClient(MONGO_URL)
	db = con[urlparse(MONGO_URL).path[1:]]
else:
	con = MongoClient('localhost', 27017)
	db = con['flask_test']

line_bot_api = LineBotApi(os.environ.get('CHANNEL_ACCESS_TOKEN'))
handler = WebhookHandler(os.environ.get('CHANNEL_SECRET'))

MONGO_URL = os.environ.get('MONGODB_URI')

if MONGO_URL:
	con = MongoClient(MONGO_URL)
	db = con[urlparse(MONGO_URL).path[1:]]
else:
	con = MongoClient('localhost', 27017)
	db = con['flask_test']

@app.route("/", methods=['POST'])
def callback():
	# get X-Line-Signature header value
	signature = request.headers['X-Line-Signature']

	# get request body as text
	body = request.get_data(as_text=True)

	# handle webhook body
	try:
		handler.handle(body, signature)
	except InvalidSignatureError:
		abort(400)

	return 'OK'

# Line Beaconイベント取得
@handler.add(BeaconEvent)
def handle_message(event):
# ビーコンに対する応答
	print(event.beacon.hwid + 'のビーコンを受信しました')
	date = datetime.now()
	now_day = date.strftime("%m月%d日")
	now_time = date.strftime("%H:%M:%S")

# 出席情報の重複確認
	attendCheckObj = db.attend.find_one({'uid': event.source.user_id, 'day': now_day, 'hwid': event.beacon.hwid})
	if attendCheckObj:
		print(attendCheckObj)
		print('既に登録済の授業です')
	else:
# 重複していないときだけ登録
		text_message = '出席を登録しました[' + now_time + ']'
		line_bot_api.reply_message(event.reply_token,[TextMessage(text=text_message)])

# 出席状況をDBに登録
		attendObj = {'uid': event.source.user_id, 'hwid': event.beacon.hwid, 'day': now_day, 'time': now_time}
		db.attend.save(attendObj)

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):

	if event.type == "message":
# 登録ユーザかどうかの確認
		userObj = db.user.find_one({'uid': event.source.user_id})
		if not userObj:
			userObj = {'uid': event.source.user_id}
			db.user.save(userObj)
			print('ユーザ情報を登録しまいた。')
		else:
			print('登録済ユーザです')

		if event.message.type == "text":
# 出席確認
			if event.message.text == '出席確認':
				historyObj = db.attend.find({'uid': event.source.user_id})
# 履歴毎にclassテーブルで授業詳細取得
# この処理ってボトルネックにならない？
				history = []
				for i in historyObj:
					classObj = db.classes.find_one({'class_id': i['hwid']})
					detail = '[' + i['day'] + i['time'] + ']\n' + classObj['class_name']
					history.append(detail)
				if len(history) == 0:
					line_bot_api.reply_message(event.reply_token,[TextSendMessage(text='出席済の授業はありません')])
				else:
					line_bot_api.reply_message(event.reply_token,[TextSendMessage(text='\n'.join(history))])
# 授業検索
			elif event.message.text == '授業検索':
				classes = ['授業一覧']
				for doc in db.classes.find({}):
					classes.append('📖' + doc['class_name'])
				line_bot_api.reply_message(event.reply_token,[TextSendMessage(text='\n'.join(classes))])
# 休講情報
			elif event.message.text == '休講情報':
				url = 'http://hack.doshisha.work/cancell/api/v1/2/today'
				target_html = requests.get(url).json()
# 表示を整え
				data = target_html['data']
				classes = target_html['cancelled_classes']
				result = []
				result.append(data['search_day'] + '\n' + data['campus'] + 'の休講情報')
				if len(classes) == 0:
					result.append('休講はありません')
				for c in classes:
					result.append(f'{c["class_name"]}({c["class_hour"]})')
				line_bot_api.reply_message(event.reply_token,[TextSendMessage(text='\n'.join(result))])
# PC教室空き状況
# API停止中のため
			# elif event.message.text == 'PC空き状況':
			# 	url = 'http://hack.doshisha.work/openpc/api/v1/2/open'
# 表示を整え
				# target_html = requests.get(url).json()
				# data = target_html['data']
				# pc = target_html['status']
				# result = []
				# result.append(data['campus'] + 'のPC空き状況(' + data['date'] + '現在)')
				# if len(pc) == 0:
				# 	result.append('現在利用できるPC教室はありません')
				# for c in pc:
				# 	result.append(f'{c["room"]}({c["free"]}/{c["max"]})')
				# line_bot_api.reply_message(event.reply_token,[TextSendMessage(text='\n'.join(result))])
# 使い方
			elif event.message.text == '使い方':
				image_url = 'https://s6.ssl.ph/trading/line-bot_box_ph/image/use.jpg'
				line_bot_api.reply_message(event.reply_token,[ImageSendMessage(original_content_url=image_url, preview_image_url=image_url)])

if __name__ == '__main__':
	port = int(os.environ.get('PORT', 5000))
	app.run(port=port)