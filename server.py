import crochet
crochet.setup()     # initialize crochet
import subprocess
from flask import Flask, request
from downloader import downloads
import json

import time
import logging

app = Flask('Scrape With Flask')

@app.route('/test', methods=['GET'])
def get_test():
    return {"success": True, "message": "OK"}
    
@app.route('/download_document', methods=['POST'])
async def post_download_document():
    #check request data
    if request.is_json is False:
        return {"error": True, "message": "Request must be JSON"}
    data = request.get_json()
    urls = data.get('urls', [])
    chatbot_id = data.get('chatbot_id', False)
    if chatbot_id is False or urls == []:
        return {"error": True, "message": "Request params invalid"}
    try:
        # download document by url store in file local
        documents_downloaded = await downloads(chatbot_id, urls)
        return {"documents_downloaded": documents_downloaded}
    except Exception as e:
        print("download_document exception:")
        print(e)
        return {"error": True, "message": str(e)}
    
if __name__=='__main__':
    app.run('0.0.0.0', 9000)