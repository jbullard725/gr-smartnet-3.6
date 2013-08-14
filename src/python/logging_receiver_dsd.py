#!/usr/env/python

from baz import op25
from gnuradio import blks2, gr, gru
from grc_gnuradio import blks2 as grc_blks2
from gnuradio import smartnet
from gnuradio.eng_option import eng_option
from gnuradio import blocks
from gnuradio import audio
from gnuradio import analog
from gnuradio import filter
from gnuradio.filter import firdes

import string
import random
import dsd
import time, datetime, math
import os

class logging_receiver(gr.hier_block2):
	def __init__(self, talkgroup, options):
		gr.hier_block2.__init__(self, "fsk_demod",
                                gr.io_signature(1, 1, gr.sizeof_gr_complex), # Input signature
                                gr.io_signature(0, 0, gr.sizeof_char)) # Output signature

		print "Starting log_receiver init()"
		self.samp_rate = samp_rate = int(options.rate)
		self.samp_per_sym = samp_per_sym = 10
		self.decim = decim = 20
		self.xlate_bandwidth = xlate_bandwidth = 24260.0
		self.xlate_offset = xlate_offset = 0
		self.channel_rate = channel_rate = op25.SYMBOL_RATE*samp_per_sym
		self.audio_mul = audio_mul = 1
		self.pre_channel_rate = pre_channel_rate = int(samp_rate/decim)

		self.squelch = squelch = -55	
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
		# Blocks
		##################################################
		print "Setting up Blocks"

		self.audiotaps = gr.firdes.low_pass(1, samp_rate, 8000, 2000, gr.firdes.WIN_HANN)

		self.prefilter_decim = int(self.rate / self.audiorate)

		#the audio prefilter is a channel selection filter.
		self.audio_prefilter = gr.freq_xlating_fir_filter_ccf(self.prefilter_decim, #decimation
								      self.audiotaps, #taps
								      0, #freq offset
								      int(samp_rate)) #sampling rate

		self.audiodemod = blks2.fm_demod_cf(self.rate/self.prefilter_decim, #rate
						    1, #audio decimation
						    4000, #deviation
						    3000, #audio passband
						    4000, #audio stopband
						    options.volume, #gain
						    75e-6) #deemphasis constant

		#the filtering removes FSK data woobling from the subaudible channel
		self.audiofilttaps = gr.firdes.high_pass(1, self.audiorate, 300, 50, gr.firdes.WIN_HANN)

		self.audiofilt = gr.fir_filter_fff(1, self.audiofilttaps)

		self.gr_quadrature_demod_cf_0 = analog.quadrature_demod_cf(1.6) #(channel_rate/(2.0 * math.pi * op25.SYMBOL_DEVIATION)))
		self.gr_freq_xlating_fir_filter_xxx_0 = filter.freq_xlating_fir_filter_ccc(decim, 
										       (firdes.low_pass(1, samp_rate, xlate_bandwidth/2, 2000)),
										       0, 
										       samp_rate)
		self.gr_fir_filter_xxx_0 = filter.fir_filter_fff(1, ((1.0/samp_per_sym,)*samp_per_sym))
		
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
			

		#here we generate a random filename in the form /tmp/[random].wav, and then use it for the wavstamp block. this avoids collisions later on. remember to clean up these files when deallocating.

		self.tmpfilename = "/tmp/%s.wav" % ("".join([random.choice(string.letters+string.digits) for x in range(8)])) #if this looks glaringly different, it's because i totally cribbed it from a blog.

		self.valve = grc_blks2.valve(gr.sizeof_float, bool(1))
		self.dsd_block_ff_0 = dsd.block_ff(dsd.dsd_FRAME_AUTO_DETECT,dsd.dsd_MOD_AUTO_SELECT,3,2,True)

		#open the logfile for appending
		self.timestampfilename = "%s/%i.txt" % (self.directory, self.talkgroup)
		self.timestampfile = open(self.timestampfilename, 'a');

		self.filename = "%s/%i.wav" % (self.directory, self.talkgroup)
		self.audiosink = smartnet.wavsink(self.filename, 1, self.audiorate, 8) #blocks.wavfile_sink(self.filename, 1, self.audiorate, 8) this version allows appending to existing files.

		self.audio_sink_0 = audio.sink(44100, "", True)


		self.timestamp = 0.0

		#print "Finishing logging receiver init()."

		self.mute() #start off muted.
		print "Connecting blocks"


	##################################################
	# Connections
		##################################################

		self.connect(self.blks2_rational_resampler_xxx_0, self.blocks_multiply_const_vxx_0)

		self.connect(self.gr_fir_filter_xxx_0 ,  self.valve, self.dsd_block_ff_0)
		self.connect(self.dsd_block_ff_0, self.blks2_rational_resampler_xxx_0)

		## Start
		self.connect(self, self.gr_freq_xlating_fir_filter_xxx_0, self.blks2_rational_resampler_xxx_1,  self.gr_quadrature_demod_cf_0, self.gr_fir_filter_xxx_0)

		## End
		# self.connect(self.blocks_multiply_const_vxx_0, self.audio_sink_0) # Plays the audio
		self.connect(self.blocks_multiply_const_vxx_0, self.audiosink) # Records the audio

		# self.valve should go somewhere
	
		#self.connect(self, self.audio_prefilter, self.audiodemod, self.valve, self.audiofilt, self.audiosink)

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

	def unmute(self):
		self.valve.set_open(bool(0))

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

