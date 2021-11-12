from tkinter import *
import tkinter.messagebox as messagebox
from PIL import Image, ImageTk
import socket, threading, sys, traceback, os

from RtpPacket import RtpPacket

CACHE_FILE_NAME = "cache-"
CACHE_FILE_EXT = ".jpg"

class Client:
	INIT = 0
	READY = 1
	PLAYING = 2
	state = INIT

	SETUP = 0
	PLAY = 1
	PAUSE = 2
	TEARDOWN = 3

	SETUP_STR = 'SETUP'
	PLAY_STR = 'PLAY'
	PAUSE_STR = 'PAUSE'
	TEARDOWN_STR = 'TEARDOWN'
	RTSP_VER = 'RTSP/1.0'

	# Initiation..
	def __init__(self, master, serveraddr, serverport, rtpport, filename):
		self.master = master
		self.master.protocol("WM_DELETE_WINDOW", self.handler)
		self.createWidgets()
		self.serverAddr = serveraddr
		self.serverPort = int(serverport)
		self.rtpPort = int(rtpport)
		self.fileName = filename
		self.rtspSeq = 0
		self.sessionId = 0
		self.requestSent = -1
		self.teardownAcked = 0
		self.connectToServer()
		self.frameNbr = 0
		self.config = []
		self.playEvent = 0

	# THIS GUI IS JUST FOR REFERENCE ONLY, STUDENTS HAVE TO CREATE THEIR OWN GUI
	def createWidgets(self):
		"""Build GUI."""
		# Create Setup button
		self.setup = Button(self.master, width=20, padx=3, pady=3)
		self.setup["text"] = "Setup"
		self.setup["command"] = self.setupMovie
		self.setup.grid(row=1, column=0, padx=2, pady=2)

		# Create Play button
		self.start = Button(self.master, width=20, padx=3, pady=3)
		self.start["text"] = "Play"
		self.start["command"] = self.playMovie
		self.start.grid(row=1, column=1, padx=2, pady=2)

		# Create Pause button
		self.pause = Button(self.master, width=20, padx=3, pady=3)
		self.pause["text"] = "Pause"
		self.pause["command"] = self.pauseMovie
		self.pause.grid(row=1, column=2, padx=2, pady=2)

		# Create Teardown button
		self.teardown = Button(self.master, width=20, padx=3, pady=3)
		self.teardown["text"] = "Teardown"
		self.teardown["command"] =  self.exitClient
		self.teardown.grid(row=1, column=3, padx=2, pady=2)

		# Create a label to display the movie
		self.label = Label(self.master, height=19)
		self.label.grid(row=0, column=0, columnspan=4, sticky=W+E+N+S, padx=5, pady=5)

	## HANDLE GUI LOGIC
	def setupMovie(self):
		"""Setup button handler."""
		if self.state == self.INIT:
			self.sendRtspRequest(self.SETUP)

	def exitClient(self):
		"""Teardown button handler."""
		if self.state == self.PLAYING:
			self.sendRtspRequest(self.PAUSE)
		self.master.destroy()
		self.sendRtspRequest(self.TEARDOWN)
		

	def pauseMovie(self):
		"""Pause button handler."""
		if self.state == self.PLAYING:
			self.sendRtspRequest(self.PAUSE)

	def playMovie(self):
		"""Play button handler."""
		if self.state == self.READY:
			self.playEvent = 1
			threading.Thread(target=self.listenRtp).start()
			self.sendRtspRequest(self.PLAY)
			
			
	##HANDLE REAL CLIENT RTSP PROTOCOL
	def sendRtspRequest(self, requestCode):
		"""Send RTSP request to the server."""
		requestHeader = ""
		self.rtspSeq+=1

		if requestCode == self.SETUP:
			threading.Thread(target=self.recvRtspReply).start()

			
			self.requestSent = self.SETUP
			requestHeader = self.SETUP_STR + " " + self.fileName + " " + self.RTSP_VER
			requestHeader+= "\nCSeq: " + str(self.rtspSeq)
			requestHeader+= "\nTransport: RTP/UDP; client_port= " + str(self.rtpPort)

		elif requestCode == self.PLAY:


			self.requestSent = self.PLAY
			requestHeader = self.PLAY_STR + " " + self.fileName + " " + self.RTSP_VER
			requestHeader+= "\nCSeq: " + str(self.rtspSeq)
			requestHeader += "\nSession: " + str(self.sessionId)

		elif requestCode == self.PAUSE:
			self.requestSent = self.PAUSE
			requestHeader = self.PAUSE_STR + " " + self.fileName + " " + self.RTSP_VER
			requestHeader+= "\nCSeq: " + str(self.rtspSeq)
			requestHeader += "\nSession: " + str(self.sessionId)

		elif requestCode == self.TEARDOWN:
			self.requestSent = self.TEARDOWN
			requestHeader = self.TEARDOWN_STR + " " + self.fileName + " " + self.RTSP_VER
			requestHeader+= "\nCSeq: " + str(self.rtspSeq)
			requestHeader += "\nSession: " + str(self.sessionId)

		self.rtspSocket.send(requestHeader.encode())
		print('\n' + str(requestHeader))


	def writeFrame(self, data):
		"""Write the received frame to a temp image file. Return the image file."""
		cachename = CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT
		file = open(cachename, "wb")
		file.write(data)
		file.close()
		return cachename

	def updateMovie(self, imageFile):
		"""Update the image file as video frame in the GUI."""
		photo = ImageTk.PhotoImage(Image.open(imageFile))
		self.label.configure(image = photo, height=300) 
		self.label.image = photo


	def connectToServer(self):
		"""Connect to the Server. Start a new RTSP/TCP session."""
		self.rtspSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		try:
			self.rtspSocket.connect((self.serverAddr, self.serverPort))
			print("connected To Server")
		except:
			messagebox.showwarning('Connection Failed', 'Connection to \'%s\' failed.' % self.serverAddr)


	#RECEIVE FIST AND LAST PACKET IN RTSP REQUEST
	def recvRtspReply(self):
		while True:
			data = self.rtspSocket.recv(256)
			if data:
				print("\n" + data.decode("utf-8"))
				self.parseRtspReply(data)

			if self.requestSent == self.TEARDOWN:
				self.rtspSocket.shutdown(socket.SHUT_RDWR)
				self.rtspSocket.close()
				break


	def listenRtp(self):
		"""Listen for RTP packets."""
		while True:
			# if self.playEvent == 0 or self.teardownAcked == 1:
			# 	break
			try:
				data , addr = self.rtpSocket.recvfrom(20480)
				if data:
					print("Received RTP packets")
					rtpPacket = RtpPacket()
					rtpPacket.decode(data)
					
					currentFrame = rtpPacket.seqNum()
					print("currentFrame: " + str(currentFrame))

					##Update new frame
					if currentFrame > self.frameNbr: 
						self.frameNbr = currentFrame
						self.updateMovie(self.writeFrame(rtpPacket.getPayload()))
			except:
				if self.playEvent == 0:
					break
				if self.teardownAcked == 1:
					self.rtpSocket.shutdown(socket.SHUT_RDWR)
					self.rtpSocket.close()
					break
					


	def parseRtspReply(self, data):
		"""Parse the RTSP reply from the server."""
		data = data.decode("utf-8")
		sessionString = data.split('\n')[2]
		seqNum =  int(data.split('\n')[2].split(' ')[1])
		statusCode = data.split(' ')[1]

		if self.requestSent == self.SETUP and statusCode == "200": 
			self.sessionId = sessionString.split(' ')[1]
			self.status = self.READY
			self.openRtpPort()

		if self.sessionId != sessionString.split(' ')[1] or self.rtspSeq != seqNum or statusCode != "200":
			return False

		if self.requestSent == self.TEARDOWN:
			self.teardownAcked = 1
			self.status = self.INIT

		if self.requestSent == self.PLAY:
			self.status = self.PLAYING

		if self.requestSent == self.PAUSE:
			self.status = self.READY
			self.playEvent = 0 

		return True


	def openRtpPort(self):
		"""Open RTP socket binded to a specified port."""

		# Create a new datagram socket to receive RTP packets from the server
		self.rtpSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

		# Set the timeout value of the socket to 0.5sec
		self.rtpSocket.settimeout(0.5)

		try:
			# Bind the socket to the address using the RTP port given by the client user.
			self.state = self.READY
			print("binding rtp port to", self.rtpPort)
			self.rtpSocket.bind(('', self.rtpPort))
		except:
			messagebox.showwarning('Unable to Bind', 'Unable to bind PORT=%d' % self.rtpPort)


	def handler(self):
		"""Handler on explicitly closing the GUI window."""
		if self.state == self.PLAYING:
			self.pauseMovie()
			self.rtpSocket.close()
		self.exitClient()
		print("GUI closed")

