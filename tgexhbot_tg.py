#!/usr/bin/python3

import logging
import json
import os
import time
import datetime
from ast import literal_eval
from queue import Queue
from threading import Thread
from telegram.ext import Updater
from telegram.ext import CommandHandler
from telegram.ext import MessageHandler 
from telegram.ext import Filters
from telegram.ext import ConversationHandler
from tgbotconvhandler import messageanalyze
from tgbotconvhandler import spiderfunction
from tgbotmodules import replytext 
# from tgbotmodules import botconfig
from tgbotmodules.spidermodules import generalcfg
from tgbotmodules import userdatastore

# from tgbotmodules import userdatastore
 
def start(bot, update, user_data, chat_data):
   user_data.clear()
   chat_data.clear()
   user_data.update({"actualusername": str(update.message.from_user.username),
                     "chat_id": update.message.chat_id}
                   )
   logger.info("Actual username is %s.", str(update.message.from_user.username))
   update.message.reply_text(text="Welcome to Nakazawa Bookstore, please show your vip card.")
   chat_data.update({'state': 'verify'})
   return STATE

def state(bot, update, user_data, chat_data):
   inputStr = update.message.text
   user_data.update({'chat_id': update.message.chat_id})
   outputDict = messageanalyze(inputStr=inputStr, 
                               user_data=user_data, 
                               chat_data=chat_data,
                               logger=logger
                              )
   user_data.update(outputDict["outputUser_data"])
   chat_data.update(outputDict["outputChat_data"])
   for text in outputDict["outputTextList"]:
      update.message.reply_text(text=text)
   if chat_data['state'] != 'END':
      state = STATE 
   else:
      # print (user_data)
      userdata = ({chat_data["virtualusername"]: user_data})
      threadName = time.asctime()
      t = Thread(target=searcheh, 
                 name=threadName, 
                 kwargs={'bot':bot,
                         'user_data':user_data,
                         'threadQ': threadQ})
      threadQ.put(t)
      user_data.clear()
      chat_data.clear() 
      logger.info("The user_data and chat_data of user %s is clear.", str(update.message.from_user.username))
      state = ConversationHandler.END
   return state

def searchIntervalCTL(bot, job, user_data=None):
    threadName = time.asctime()
    t = Thread(target=searcheh, 
               name=threadName, 
               kwargs={'bot':bot,
                        'user_data':user_data,
                        'threadQ': threadQ})
    threadQ.put(t)


def searcheh(bot, threadQ, job=None, user_data=None):
   logger.info("Search is beginning")
   if user_data:
      for ud in user_data:
         user_data[ud].update({'userpubchenn': False,'resultToChat': True})
         logger.info("User %s has finished profile setting process, test search is begining.", user_data[ud]['actualusername'])
      # print (user_data)
      spiderDict = user_data
      toTelegramDict = spiderfunction(logger=logger, spiderDict=spiderDict)
   else:
      spiderDict = userdatastore.getspiderinfo()
      toTelegramDict = spiderfunction(logger=logger)
      logger.info("All users' search has been completed, begin to send the result")
   if toTelegramDict:
      for td in toTelegramDict:

         chat_idList = []     
         if spiderDict[td].get('chat_id') and spiderDict[td]['resultToChat'] == True:
            chat_idList.append(spiderDict[td]['chat_id'])
         if spiderDict[td]["userpubchenn"] == True and generalcfg.pubChannelID:      # Public channel id might be empty
            chat_idList.append(generalcfg.pubChannelID)
         logger.info("Begin to send user %s's result.", td)
         
         for chat_id in chat_idList:
            if len(toTelegramDict[td]) == 0:
               messageDict = {"messageCate": "message",
                              "messageContent": ["------Could not find any new result for {0}------".format(str(td))]}
               channelmessage(bot=bot, messageDict=messageDict, chat_id=chat_id)
               continue
            messageDict = {"messageCate": "message",
                           "messageContent": ["------This is the result of {0}------".format(str(td))]}
            channelmessage(bot=bot, messageDict=messageDict, chat_id=chat_id)
            for manga in toTelegramDict[td]:
            #    for obj in toTelegramDict[td][result]:
               if manga.previewImageObj:
                #   print(manga.previewImageObj.getbuffer().nbytes)
                  messageDict = {'messageCate': "photo", "messageContent": [manga.previewImageObj]}
                  channelmessage(bot=bot, messageDict=messageDict, chat_id=chat_id)
               messageDict = {'messageCate': "message", "messageContent": ['{0}\n{1}'.format(manga.title, manga.url)]}
               channelmessage(bot=bot, messageDict=messageDict, chat_id=chat_id)
         logger.info("User {0}'s result has been sent.".format(td))
      logger.info("All users' result has been sent.")
   else: 
      logger.info("Could not gain any new result to users.")         
      messageDict = {"messageCate": "message", "messageContent": ["We do not have any new result"]}
      channelmessage(bot=bot, messageDict=messageDict, chat_id=generalcfg.pubChannelID)
   threadQ.task_done()

def retryDocorator(func, retry=generalcfg.timeoutRetry):
   '''This simple retry decorator provides a try-except looping to the channelmessage function to
      overcome network fluctuation.'''

   def wrapperFunction(*args, **kwargs):
      err = 0 
      for err in range(retry):
         try:
            func(*args, **kwargs)
            break
         except Exception as error:
           err += 1
           logger.warning(str(error))
      else:
         logger.warning('Retry limitation reached')
         
      return
   return wrapperFunction

@retryDocorator
def channelmessage(bot, messageDict, chat_id):
   ''' All the functions containing user interaction would use this function to send messand 
       to user.'''
   messageContent = messageDict["messageContent"]
   for mC in messageContent:
      if messageDict['messageCate'] == 'photo':
         mC.seek(0)
         bot.send_photo(chat_id=chat_id, photo=mC)
      else:
         bot.send_message(chat_id=chat_id, text=mC)
   return None

def thread_containor(threadQ):
   # Put any threads to this function and it would run separately.
   # But please remember put the threadQ obj into the functions in those threads to use threadQ.task_done().
   # Or the program would stock.
   threadCounter = 0
   while True:
      t = threadQ.get()
      logger.info('Added a new thread to thread containor - {0} '.format(t.name))
      t.start()
      threadCounter += 1
      if threadCounter == 1:  # This condition limit the amount of threads running simultaneously.
         t.join() 
         threadCounter = 0

def autoCreateJob(job):
   job.run_repeating(searchIntervalCTL, interval=generalcfg.interval, first=5)

def cancel(bot, update, user_data, chat_data):  
   update.message.reply_text(text=replytext.UserCancel)
   logger.info("User %s has canceled the process.", str(update.message.from_user.username))
   user_data.clear()
   chat_data.clear()
   logger.info("The user_data and chat_data of user %s has cleared", str(update.message.from_user.username))
   return ConversationHandler.END

def error(bot, update, error):
   logger.warning('Update "%s" caused error "%s"', update, error)

def main():
   if generalcfg.proxy:
      updater = Updater(token=generalcfg.token, request_kwargs={'proxy_url': generalcfg.proxy[0]})
   else:   
      updater = Updater(token=generalcfg.token)
   dp = updater.dispatcher
   job= updater.job_queue
   conv_handler = ConversationHandler(
                  entry_points=[CommandHandler('start', start, pass_user_data=True, pass_chat_data=True)],
                  states={STATE: [MessageHandler(Filters.text, state, pass_user_data=True, pass_chat_data=True)]
                  },
                  fallbacks=[CommandHandler('cancel', cancel, pass_user_data=True, pass_chat_data=True)],
   )
   dp.add_handler(conv_handler)
   dp.add_error_handler(error)
   autoCreateJob(job=job)
   tc = Thread(target=thread_containor, 
               name='tc', 
               kwargs={'threadQ': threadQ},
               daemon=True)
   tc.start()
   logger.info('Spider thread containor initiated.')
   updater.start_polling(poll_interval=1.0, timeout=1.0)
   logger.info('Bot initiated.')
   updater.idle()


logging.basicConfig(format='%(asctime)s - %(module)s.%(funcName)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)
logging.getLogger('requests').setLevel(logging.CRITICAL)
threadQ = Queue()  # This queue object put the spider function into the thread containor 
                   # Using this thread containor wound also limits the download function thread
                   # to prevent e-h to ban IP.
(STATE) = range(1)

if __name__ == '__main__':
   main()