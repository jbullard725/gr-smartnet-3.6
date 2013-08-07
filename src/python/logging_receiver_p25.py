#!/usr/env/python

from baz import message_callback
from baz import op25
from baz import op25_traffic_pane
from gnuradio import blks2, gr, gru
from grc_gnuradio import blks2 as grc_blks2
from gnuradio import smartnet
from gnuradio.eng_option import eng_option
from gnuradio.gr import firdes
from gnuradio import blocks
from gnuradio import audio

import string
import random
import time, datetime, math
import os

class logging_receiver_p25(gr.hier_block2):
	def __init__(self, talkgroup, options):
		gr.hier_block2.__init__(self, "fsk_demod",
                                gr.io_signature(1, 1, gr.sizeof_gr_complex), # Input signature
                                gr.io_signature(0, 0, gr.sizeof_char)) # Output signature

		#print "Starting log_receiver init()"
		self.samp_rate = samp_rate = int(options.rate)
		self.samp_per_sym = samp_per_sym = 5+1
		self.decim = decim = 20
		self.xlate_bandwidth = xlate_bandwidth = 24260.0
		self.xlate_offset = xlate_offset = 0
		self.channel_rate = channel_rate = op25.SYMBOL_RATE*samp_per_sym
		self.audio_mul = audio_mul = 2
		self.pre_channel_rate = pre_channel_rate = int(samp_rate/decim)


		self.auto_tune_offset = auto_tune_offset = 0	
		self.audiorate = 44100 #options.audiorate
		self.rate = options.rate
		self.talkgroup = talkgroup
		self.directory = options.directory

		if options.squelch is None:
			options.squelch = 28

		if options.volume is None:
			options.volume = 3.0


		##################################################
		# Message Queues
		##################################################
		op25_fsk4_0_msgq_out = baz_message_callback_0_msgq_in = gr.msg_queue(2)
		op25_decoder_simple_0_msgq_out = op25_traffic_pane_0_msgq_in = gr.msg_queue(2)

		##################################################
		# Blocks
		##################################################

		self.op25_fsk4_0 = op25.op25_fsk4(channel_rate=channel_rate, auto_tune_msgq=op25_fsk4_0_msgq_out,)
		self.op25_decoder_simple_0 = op25.op25_decoder_simple(key="",traffic_msgq=op25_decoder_simple_0_msgq_out,)
		self.gr_quadrature_demod_cf_0 = gr.quadrature_demod_cf((channel_rate/(2.0 * math.pi * op25.SYMBOL_DEVIATION)))
		self.gr_freq_xlating_fir_filter_xxx_0 = gr.freq_xlating_fir_filter_ccc(decim, 
										       (firdes.low_pass(1, samp_rate, xlate_bandwidth/2, 4000)),
										       0, 
										       samp_rate)
		self.gr_fir_filter_xxx_0 = gr.fir_filter_fff(1, ((1.0/samp_per_sym,)*samp_per_sym))



		
		self.blocks_multiply_const_vxx_0 = blocks.multiply_const_vff((10.**(audio_mul/10.), ))
		self.blks2_rational_resampler_xxx_1 = blks2.rational_resampler_ccc(
			interpolation=channel_rate,
			decimation=pre_channel_rate,
			taps=None,
			fractional_bw=None,
		)
		self.blks2_rational_resampler_xxx_0 = blks2.rational_resampler_fff(
			interpolation=self.audiorate,
			decimation=8000,
			taps=None,
			fractional_bw=None,
		)
		self.baz_message_callback_0 = message_callback.message_callback(msgq=baz_message_callback_0_msgq_in,	callback=auto_tune_offset	, msg_part="arg1", custom_parts="",	dummy=False)
			

		#here we generate a random filename in the form /tmp/[random].wav, and then use it for the wavstamp block. this avoids collisions later on. remember to clean up these files when deallocating.

		self.tmpfilename = "/tmp/%s.wav" % ("".join([random.choice(string.letters+string.digits) for x in range(8)])) #if this looks glaringly different, it's because i totally cribbed it from a blog.

		self.valve = grc_blks2.valve(gr.sizeof_float, bool(1))


		#open the logfile for appending
		self.timestampfilename = "%s/%i.txt" % (self.directory, self.talkgroup)
		self.timestampfile = open(self.timestampfilename, 'a');

		self.filename = "%s/%i.wav" % (self.directory, self.talkgroup)
		self.audiosink = smartnet.wavsink(self.filename, 1, self.audiorate, 8) #this version allows appending to existing files.

		self.audio_sink_0 = audio.sink(44100, "", True)


		self.timestamp = 0.0

		#print "Finishing logging receiver init()."

		self.mute() #start off muted.



	##################################################
	# Connections
		##################################################
		self.connect((self.gr_freq_xlating_fir_filter_xxx_0, 0), (self.blks2_rational_resampler_xxx_1, 0))
		self.connect((self.blks2_rational_resampler_xxx_1, 0), (self.gr_quadrature_demod_cf_0, 0))
		self.connect((self.gr_quadrature_demod_cf_0, 0), (self.gr_fir_filter_xxx_0, 0))
		self.connect((self.blks2_rational_resampler_xxx_0, 0), (self.blocks_multiply_const_vxx_0, 0))

		self.connect((self.gr_fir_filter_xxx_0, 0), (self.op25_fsk4_0, 0))
		self.connect((self.op25_fsk4_0, 0), (self.op25_decoder_simple_0, 0))
		self.connect((self.op25_decoder_simple_0, 0), (self.blks2_rational_resampler_xxx_0, 0))

		## Start
		self.connect(self, (self.gr_freq_xlating_fir_filter_xxx_0, 0))

		## End
		self.connect((self.blocks_multiply_const_vxx_0, 0), (self.audio_sink_0,0))


#######################




	def __del__(self):
		#self.close()
		#self.audiosink.close()
		#os.system("rm %s" % self.tmpfilename) #remove the temp file you used for wav stamping
		self.timestampfile.close()

	def tuneoffset(self, target_freq, rffreq):
		self.gr_freq_xlating_fir_filter_xxx_0.set_center_freq(rffreq - target_freq*1e6)
		print "Offset set to: %f" % (target_freq*1e6-rffreq)
		self.freq = target_freq

	def getfreq(self, rffreq):
		return self.freq

	def close(self): #close out and quit!
		self.mute() #make sure you aren't going to be writing
		self.audiosink.close() #if you write after this it's going to throw all the errors


	def mute(self):
		self.valve.set_open(bool(1))
#		self.prefiltervalve.set_open(bool(1))

	def unmute(self):
		self.valve.set_open(bool(0))
#		self.prefiltervalve.set_open(bool(0))
		if (self.timeout()) >= 3:
			self.stamp()

		self.timestamp = time.time()

	def timeout(self):
		return time.time() - self.timestamp

	def stamp(self):
		#print "Stamp says the current wavtime is %f" % self.audiosink.get_time()
		current_wavtime = self.audiosink.get_time() #gets the time in fractional seconds corresponding to the current position in the audio file
		current_timestring = time.strftime("%m/%d/%y %H:%M:%S")
		current_timestampstring = str(datetime.timedelta(seconds=current_wavtime)) + ": " + current_timestring + "\n"
		self.timestampfile.write(current_timestampstring)
		self.timestampfile.flush() #so you can follow along

