import asyncio
import aiohttp
import os
import shutil
import tempfile
import magic
import uuid
import json
from bs4 import BeautifulSoup, Tag, NavigableString, Comment
from llama_index.core import SimpleDirectoryReader
from janome.tokenizer import Tokenizer
from spellchecker import SpellChecker
import re
from urllib.parse import urljoin
from playwright.async_api import async_playwright
import requests
import time
import logging
import string
from typing import List, Union
import sys
import argparse

DELAY_TIME = 0.1
def get_extension_from_mime(mime_type):
    # Return file extension based on MIME type
    with open('downloader_extensions_config.json', 'r') as f:
        # Load the JSON data
        extensions = json.load(f)
        return extensions.get(mime_type, None)  # Return None for unknown types
    
def is_html(url):
    try:
        # Use GET instead of HEAD for better compatibility
        response = requests.get(url, timeout=10, stream=True)
        
        # Check Content-Type header
        content_type = response.headers.get('Content-Type', '').lower()
        if 'text/html' in content_type:
            return True

        # If Content-Type is missing or unclear, check the first 1024 bytes of content
        for chunk in response.iter_content(1024):
            if b"<html" in chunk.lower():
                return True
            break  # No need to read more than one chunk

    except requests.RequestException:
        pass  # Handle network errors gracefully
    
    return False

async def download_html_page(chatbot_directory, document_metadata):    
    url = document_metadata['url']
    print(f"download_html_page url {url}")
    """Fetch content from a URL using Playwright."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        content = False
        try:
            await page.goto(url, timeout=10000)  # 10s timeout
            await page.wait_for_load_state("load")
            await page.wait_for_timeout(2000)
            content = await page.content()  # Get HTML content
            print(f"Downloaded: {url}")
        except Exception as e:
            print(f"Failed: {url} -> {e}")
        finally:
            await browser.close()
        if content == False:
            return False
        
        soup = BeautifulSoup(clean_html(content), 'html.parser')
        content = str(soup.prettify())
        extension = ".html"
        mime_type = "text/html"
        final_path = chatbot_directory+str(uuid.uuid4()) + extension
        with open(final_path, "w", encoding="UTF-8") as f:
            f.write(content)
            
        print(f"File has been saved as {final_path} with MIME type {mime_type}")
        # add final path and extension to document metadata
        document_metadata['final_path'] = final_path
        document_metadata['extension'] = extension
        return document_metadata
    
MEANINGFUL_TAGS = {'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'a', 'ul', 'ol', 'li', 'table', 'tr', 'th', 'td',
                    'blockquote', 'pre', 'img', 'video', 'audio'}
ALLOWED_ATTRS = {'a': ['href', 'title'], 'img': ['src', 'alt'], 'video': ['src'], 'audio': ['src']}
REMOVE_TAGS = {'header', 'footer', 'nav', 'script', 'style'}

def clean_html(html: str) -> str:
    """
    Clean and format HTML content.

    Args:
        html (str): Input HTML string.

    Returns:
        str: Cleaned and formatted HTML string.
    """
    def process_tag(tag: Union[Tag, NavigableString]) -> List[str]:
        if isinstance(tag, NavigableString):
            return [str(tag).strip()] if tag.strip() else []
        
        if tag.name not in MEANINGFUL_TAGS:
            return sum((process_tag(child) for child in tag.children), [])
        
        attrs = ' '.join(f'{k}="{v}"' for k, v in tag.attrs.items() if k in ALLOWED_ATTRS.get(tag.name, []))
        opening_tag = f"<{tag.name}{f' {attrs}' if attrs else ''}>"
        closing_tag = f"</{tag.name}>"
        
        content = ' '.join(sum((process_tag(child) for child in tag.children), []))
        return [f"{opening_tag}{content}{closing_tag}"]

    print("clean_html")
    try:        
        soup = BeautifulSoup(html, 'lxml')
        # Find all comments
        comments = soup.find_all(string=lambda text: isinstance(text, Comment))

        # Remove all comments
        for comment in comments:
            comment.extract()

        # Remove elements with inline style="display: none"
        for tag in soup.find_all(style=True):
            if tag is not None and tag.get_text() and tag['style'] is not None:
                style = tag['style'].translate({ord(c): None for c in string.whitespace})
                if ('display:none' in style) or ('visibility:hidden' in style):
                    tag.decompose()  # Decompose completely removes the tag
            
    
        # Remove tags with empty content
        for tag in soup.find_all():
            if not tag.contents or not ''.join(tag.stripped_strings):
                tag.decompose()
        for tag in soup.find_all(REMOVE_TAGS):
            tag.decompose()

        processed_content = sum((process_tag(tag) for tag in soup.body.children 
                                 if isinstance(tag, Tag) or (isinstance(tag, NavigableString) and tag.strip())), [])
        
        formatted_output = ' '.join(processed_content)
        formatted_output = re.sub(r'\n{3,}', '\n\n', formatted_output)
        print("clean_html finish")
        return formatted_output.strip()
    except Exception as e:
        print(f"An error occurred: {e}")
        return ""
async def download_file(chatbot_directory, document_metadata, delay):
    await asyncio.sleep(delay)
    if(is_html(document_metadata['url'])):
        return await download_html_page(chatbot_directory, document_metadata)
    else: 
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.6778.33 Safari/537.36"}
        async with aiohttp.ClientSession(headers=headers) as session:
            try:
                url = document_metadata['url']
                async with session.get(url) as response:
                    print(f"download url {url}")
                    # print(f"response {str(response)}")
                    with tempfile.NamedTemporaryFile() as file:
                        while True:
                            chunk = await response.content.read()
                            if not chunk:
                                break
                            file.write(chunk)
                            # print(f"chunk file {str(chunk)}")
                        file.flush()  # Ensure all data is written to the file
                        
                        # Process the file as needed
                        file.seek(0)  # Go back to the start of the file if you need to read it
                        print(f"Downloaded file {file.name}")
                        mime_type = magic.from_file(file.name, mime=True)
                        print(f"detected mime_type {mime_type}")
                        extension = get_extension_from_mime(mime_type)                    
                        print(f"detected extension {extension}")
                        if extension:
                            # Save the final file with the correct extension
                            final_path = chatbot_directory+str(uuid.uuid4()) + extension
                            shutil.copyfile(file.name, final_path)
                            print(f"File has been saved as {final_path} with MIME type {mime_type}")
                            # add final path and extension to document metadata
                            document_metadata['final_path'] = final_path
                            document_metadata['extension'] = extension
                            return document_metadata
                        else:
                            print("Downloaded file type is not supported by LlamaIndex.")
                            return False
            except aiohttp.ClientConnectionError:
                print(f"Connection error {url}") 
                return False
            except aiohttp.ClientResponseError:
                print(f"Invalid response {url}")
                return False            

async def downloads(chatbot_id, urls):
    print("download documents")
    chatbot_directory = "document_chatbot/" + chatbot_id + "/"
    if not os.path.exists("document_chatbot/"):
        os.mkdir("document_chatbot/")
    if os.path.exists(chatbot_directory):
        shutil.rmtree(chatbot_directory)    
    os.mkdir(chatbot_directory)
    urls_metadata = []
    for url in urls:
        urls_metadata.append({
            'title': "",
            'tags': [],
            'url': url,
            'priority': 'high'
        })
    tasks = []
    i = 0
    for document_metadata in urls_metadata:
        delay_time = i*DELAY_TIME
        tasks.append(download_file(chatbot_directory, document_metadata, delay_time))
        i = i + 1
    documents_downloaded = await asyncio.gather(*tasks)
    print("download documents finish")
    return documents_downloaded

def clean_mixed_text(text):
    # Initialize the tokenizer and spell checker
    t = Tokenizer()
    spell = SpellChecker()
    tokens = t.tokenize(text, wakati=True)

    cleaned_tokens = []
    previous_token_is_english = False

    for token in tokens:
        if token is None:
            continue
        # Determine if the token is an English word
        is_english = re.match(r'^[a-zA-Z]+$', token)
        
        # Correct spelling mistakes in English words using SpellChecker
        # if is_english:
        #     token = spell.correction(token)
        if token is None:
            continue
        # Add spaces appropriately between English and Japanese words
        if cleaned_tokens:
            if is_english and not previous_token_is_english:
                cleaned_tokens.append(' ')
            elif not is_english and previous_token_is_english:
                cleaned_tokens.append(' ')
        
        cleaned_tokens.append(token)
        previous_token_is_english = is_english

    # Join tokens to create text
    cleaned_text = ''.join(cleaned_tokens)
    
    # Remove extra spaces within sentences
    cleaned_text = re.sub(r'\s+', ' ', cleaned_text)
    # Adjust spaces around punctuation marks
    cleaned_text = re.sub(r' ([.,!?;:])', r'\1', cleaned_text)
    # Remove leading and trailing spaces
    cleaned_text = cleaned_text.strip()
    # Remove spaces between Japanese characters
    cleaned_text = re.sub(r'(?<=[\u3040-\u30FF\u4E00-\u9FFF]) (?=[\u3040-\u30FF\u4E00-\u9FFF])', '', cleaned_text)

    return cleaned_text

def parse_args():
    parser = argparse.ArgumentParser(description="Async downloader")
    parser.add_argument('--name', required=True, help='Name of the download task')
    parser.add_argument('--urls', nargs='+', required=True, help='List of URLs to download')
    args = parser.parse_args()

    # Additional validation
    if not args.name.strip():
        print("Error: --name cannot be empty or just spaces.")
        sys.exit(1)

    filtered_urls = [url for url in args.urls if url.strip()]
    if not filtered_urls:
        print("Error: --urls must contain at least one non-empty URL.")
        sys.exit(1)
    return args.name, filtered_urls

if __name__=='__main__':
    name, urls = parse_args()
    print(name, urls)
    asyncio.run(downloads(name, urls))