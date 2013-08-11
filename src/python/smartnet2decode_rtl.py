#!/usr/bin/env python
""" 
	This program decodes the Motorola SmartNet II trunking protocol from the control channel
	Tune it to the control channel center freq, and it'll spit out the decoded packets.
	In what format? Who knows.

	Based on your AIS decoding software, which is in turn based on the gr-pager code and the gr-air code.
"""

#define OSW_BACKGROUND_IDLE     0x02f8
#define OSW_FIRST_CODED_PC      0x0304
#define OSW_FIRST_NORMAL        0x0308
#define OSW_FIRST_TY2AS1        0x0309
#define OSW_EXTENDED_FCN        0x030b                      
#define OSW_AFFIL_FCN           0x030d
#define OSW_TY2_AFFILIATION     0x0310
#define OSW_TY1_STATUS_MIN      0x0310
#define OSW_TY2_MESSAGE         0x0311
#define OSW_TY1_STATUS_MAX      0x0317
#define OSW_TY1_ALERT           0x0318
#define OSW_TY1_EMERGENCY       0x0319
#define OSW_TY2_CALL_ALERT      0x0319
#define OSW_FIRST_ASTRO         0x0321
#define OSW_SYSTEM_CLOCK        0x0322
#define OSW_SCAN_MARKER         0x032b
#define OSW_EMERG_ANNC          0x032e
#define OSW_AMSS_ID_MIN         0x0360
#define OSW_AMSS_ID_MAX         0x039f
#define OSW_CW_ID               0x03a0
#define OSW_SYS_NETSTAT         0x03bf
#define OSW_SYS_STATUS          0x03c0

from gnuradio import gr, gru, blks2, optfir, digital
from gnuradio import audio
from gnuradio import eng_notation
from gnuradio import uhd
from fsk_demod import fsk_demod
from optparse import OptionParser
from gnuradio.eng_option import eng_option
from gnuradio import smartnet
import osmosdr
from gnuradio import digital

import time
import gnuradio.gr.gr_threading as _threading
import csv

class top_block_runner(_threading.Thread):
    def __init__(self, tb):
        _threading.Thread.__init__(self)
        self.setDaemon(1)
        self.tb = tb
        self.done = False
        self.start()

    def run(self):
        self.tb.run()
        self.done = True

class my_top_block(gr.top_block):
	def __init__(self, options, queue):
		gr.top_block.__init__(self)

		if options.filename is not None:
			self.fs = gr.file_source(gr.sizeof_gr_complex, options.filename)
			self.rate = options.rate

		else:
			#self.u = uhd.usrp_source(options.addr,
			#						 io_type=uhd.io_type.COMPLEX_FLOAT32,
			#						 num_channels=1)

                    
                    self.rtl = osmosdr.source_c( args="nchan=" + str(1) + " " + ""  )
                    self.rtl.set_sample_rate(options.rate)
                    self.rate = options.rate #self.rtl.get_samp_rate()
                    self.rtl.set_center_freq(options.centerfreq, 0)
                    #self.rtl.set_freq_corr(options.ppm, 0)
                    
		
                    self.centerfreq = options.centerfreq
                    print "Tuning to: %fMHz" % (self.centerfreq - options.error)
                    if not(self.tune(options.centerfreq - options.error)):
			print "Failed to set initial frequency"

                    if options.gain is None: #set to halfway
#			g = self.u.get_gain_range()
#			options.gain = (g.start()+g.stop()) / 2.0
			options.gain = 10
			# TODO FIX^

                    print "Setting gain to %i" % options.gain
                    #self.rtl.set_gain(options.gain, 0)
                    self.rtl.set_gain(10, 0)
                    
                    self.rtl.set_if_gain(20,0)
                    self.rtl.set_bb_gain(20,0)
                    #self.rtl.set_gain_mode(1,0)

		print "Samples per second is %i" % self.rate

		self._syms_per_sec = 3600;


		options.samples_per_second = self.rate
		options.syms_per_sec = self._syms_per_sec
		options.gain_mu = 0.01
		options.mu=0.5
		options.omega_relative_limit = 0.3
		options.syms_per_sec = self._syms_per_sec
		options.offset = options.centerfreq - options.freq
		print "Control channel offset: %f" % options.offset

                #taps = gr.firdes.low_pass(1.0, self.rate, 6000, 5000, gr.firdes.WIN_HANN)
                #self.tuner = gr.freq_xlating_fir_filter_ccf(1, taps,20000, self.rate)

  #first_decim = 10#int(self.rate / options.syms_per_sec)
                self.offset = gr.sig_source_c(self.rate, gr.GR_SIN_WAVE,
                                              20000, 1.0, 0.0)
                self.mixer = gr.multiply_cc()

		self.demod = fsk_demod(options)
		self.start_correlator = gr.correlate_access_code_tag_bb("10101100",
		                                                        0,
		                                                        "smartnet_preamble") #should mark start of packet
		self.smartnet_deinterleave = smartnet.deinterleave()
		self.smartnet_crc = smartnet.crc(queue)

                #rerate = float(self.rate / float(first_decim)) / float(7200)
                #print "resampling factor: %f\n" % rerate
                
                #if rerate.is_integer():
                #    print "using pfb decimator\n"
                #    self.resamp = blks2.pfb_decimator_ccf(int(rerate))
                #else:
                #    print "using pfb resampler\n"
                #    self.resamp = blks2.pfb_arb_resampler_ccf(1 / rerate)

		if options.filename is None:
			#self.connect(self.u, self.demod)
                    self.connect(self.rtl, (self.mixer, 0))
                    self.connect(self.offset, (self.mixer, 1))                    
                    self.connect(self.mixer, self.demod)
                        #self.connect(self.rtl, self.demod)
		else:
			self.connect(self.fs, self.demod)

		self.connect(self.demod, self.start_correlator, self.smartnet_deinterleave, self.smartnet_crc)

		#hook up the audio patch
		if options.audio:
			self.audiorate = 48000
			self.audiotaps = gr.firdes.low_pass(1, self.rate, 8000, 2000, gr.firdes.WIN_HANN)
			self.prefilter_decim = int(self.rate / self.audiorate) #might have to use a rational resampler for audio
			print "Prefilter decimation: %i" % self.prefilter_decim
			self.audio_prefilter = gr.freq_xlating_fir_filter_ccf(self.prefilter_decim, #decimation
									      self.audiotaps, #taps
									      0, #freq offset
									      self.rate) #sampling rate

			#on a trunked network where you know you will have good signal, a carrier power squelch works well. real FM receviers use a noise squelch, where
			#the received audio is high-passed above the cutoff and then fed to a reverse squelch. If the power is then BELOW a threshold, open the squelch.
			#self.squelch = gr.pwr_squelch_cc(options.squelch, #squelch point
			#								   alpha = 0.1, #wat
			#								   ramp = 10, #wat
			#								   gate = False)

			self.audiodemod = blks2.fm_demod_cf(self.rate/self.prefilter_decim, #rate
							    1, #audio decimation
							    4000, #deviation
							    3000, #audio passband
							    4000, #audio stopband
							    1, #gain
							    75e-6) #deemphasis constant

			#the filtering removes FSK data woobling from the subaudible channel (might be able to combine w/lpf above)
			self.audiofilttaps = gr.firdes.high_pass(1, self.audiorate, 300, 50, gr.firdes.WIN_HANN)
			self.audiofilt = gr.fir_filter_fff(1, self.audiofilttaps)
			self.audiogain = gr.multiply_const_ff(options.volume)
			self.audiosink = audio.sink (self.audiorate, "")
#			self.audiosink = gr.wavfile_sink("test.wav", 1, self.audiorate, 8)

			#self.mute()

			if options.filename is None:
				#self.connect(self.u, self.audio_prefilter)
                                self.connect(self.rtl, self.audio_prefilter)
			else:
				self.connect(self.fs, self.audio_prefilter)

#			self.connect(self.audio_prefilter, self.squelch, self.audiodemod, self.audiofilt, self.audiogain, self.audioresamp, self.audiosink)
#	real		self.connect(self.audio_prefilter, self.squelch, self.audiodemod, self.audiofilt, self.audiogain, self.audiosink)
			self.connect(self.audio_prefilter, self.audiodemod, self.audiofilt, self.audiogain, self.audiosink)

###########SUBCHANNEL DECODING EXPERIMENT###########
			#here we set up the low-pass filter for audio subchannel data decoding. gain of 10, decimation of 10.
#			self.subchannel_decimation = 50
#			self.subchannel_gain = 10
#			self.subchannelfilttaps = gr.firdes.low_pass(self.subchannel_gain, self.audiorate, 200, 40, firdes.WIN_HANN)
#			self.subchannelfilt = gr.fir_filter_fff(self.subchannel_decimation, self.subchannelfilttaps)
#			self.subchannel_syms_per_sec = 150
#			self.subchannel_samples_per_symbol = (self.audiorate / self.subchannel_decimation) / self.subchannel_syms_per_sec
#			print "Subchannel samples per symbol: %f" % self.subchannel_samples_per_symbol
#			self.subchannel_clockrec = gr.clock_recovery_mm_ff(self.subchannel_samples_per_symbol,
#															   0.25*0.01*0.01,
#															   0.5,
#															   0.01,
#															   0.3)
#			self.subchannel_slicer = gr.binary_slicer_fb()
#			self.subchannel_correlator = gr.correlate_access_code_bb("01000",0)
#			self.subchannel_framer = smartnet.subchannel_framer()
#			self.subchannel_sink = gr.null_sink(1); #just so it doesn't bitch until we do something with it
#			self.connect(self.audiodemod, self.subchannelfilt, self.subchannel_clockrec, self.subchannel_slicer, self.subchannel_correlator, self.subchannel_framer, self.subchannel_sink)
		
	def tune(self, freq):
		result = self.rtl.set_center_freq(freq)
		return True

	def tuneoffset(self, target_freq, rffreq):
		#print "Setting offset; target freq is %f, Center freq is %f" % (target_freq, rffreq)
		self.audio_prefilter.set_center_freq(rffreq-target_freq*1e6)

	def setvolume(self, vol):
		self.audiogain.set_k(vol)

	def mute(self):
		self.setvolume(0)
	def unmute(self, volume):
		self.setvolume(volume)

def getfreq(chanlist, cmd):
	if chanlist is None:
		if cmd < 0x2d0:		
			freq = float(cmd * 0.025 + 851.0125)
		else:
			freq = None
	else:
		if chanlist.get(str(cmd), None) is not None:
			freq = float(chanlist[str(cmd)])
		else:
			freq = None

	return freq




def commandstring(c):
    if c == 0x0310:
        return 'TY1_STATUS_MIN'
    if c == 0x0310:
        return 'TY2_AFFILIATION'
    if c == 0x030d:
        return 'AFFIL_FCN'
    if c == 0x030b:
        return 'EXTENDED_FCN'
    if c == 0x0309:
        return 'FIRST_TY2AS1'
    if c == 0x0304:
        return 'FIRST_CODED_PC'
    if c == 0x0308:
        return 'FIRST_NORMAL'
    if c == 0x02f8:
        return 'BACKGROUND_IDLE'
    if c == 0x3c0:
        return 'SYS_STATUS'
    if c == 0x03bf:
        return 'SYS_NETSTAT'
    if c == 0x03a0:
        return 'CW_ID'
    if c == 0x039f:
        return 'AMSS_ID_MAX'
    if c == 0x0360:
        return 'AMSS_ID_MIN'
    if c == 0x032e:
        return 'EMERG_ANNC'
    if c == 0x032b:
        return 'SCAN_MARKER'
    if c == 0x0322:
        return 'SYSTEM_CLOCK'
    if c == 0x0319:
        return 'EMERGENCY'
    if c == 0x0318:
        return 'ALERT'
    if c == 0x0317:
        return 'STATUS_MAX'
    if c == 0x0311:
        return 'MESSAGE'
    return hex(c)

def parsefreq(s, chanlist):
	retfreq = None
	[address, groupflag, command] = s.split(",")
	command = int(command)
	address = int(address) & 0xFFF0
	groupflag = bool(groupflag)

	if chanlist is None:
		if command < 0x2d0:
			retfreq = getfreq(chanlist, command)

	else:
		if chanlist.get(str(command), None) is not None: #if it falls into the channel somewhere
			retfreq = getfreq(chanlist, command)
	return [retfreq, address] # mask so the squelch opens up on the entire group

def parse(s, shorttglist, longtglist, chanlist, elimdupes):
	#this is the main parser. it takes in commands in the form "address,command" (no quotes of course) and outputs text via print
	#it is also responsible for using the talkgroup list, if any
	[address, groupflag, command] = s.split(",")
	command = int(command)
	address = int(address)
	lookupaddr = address & 0xFFF0
	groupflag = bool(groupflag)

        if command != 0x03bf and command != 0x032b and command != 0x03c0:
            print "%s \t %s \t[ %d ] \t " % (hex(command), commandstring(command), address)
	if longtglist is not None and longtglist.get(str(lookupaddr), None) is not None:
		longname = longtglist[str(lookupaddr)] #the mask is to screen out extra status bits, which we can add in later (see the RadioReference.com wiki on SmartNet Type II)
	else:
		longname = None

	if shorttglist is not None and shorttglist.get(str(lookupaddr), None) is not None:
		shortname = shorttglist[str(lookupaddr)]
	else:
		shortname = None

	retval = None


	if command == 0x30B and groupflag is True and lastmsg.get("command", None) == 0x308 and address & 0x2000 and address & 0x0800:
		retval = "SysID: Sys #" + hex(lastmsg["address"]) + " on " + str(getfreq(chanlist, address & 0x3FF))

	else:
		if getfreq(chanlist, command) is not None and dupes.get(command, None) != address:
			retval = "Freq assignment: " + str(shortname) + " (" + str(address) + ")" + " @ " + str(getfreq(chanlist, command)) + " (" + str(longname) + ")"

	if elimdupes is True:
		dupes[command] = address

	lastlastmsg = lastmsg
	lastmsg["command"]=command
	lastmsg["address"]=address

	return retval


def main():
	# Create Options Parser:
	parser = OptionParser (option_class=eng_option, conflict_handler="resolve")
	expert_grp = parser.add_option_group("Expert")

	parser.add_option("-f", "--freq", type="eng_float", default=866.9625e6,
						help="set control channel frequency to MHz [default=%default]", metavar="FREQ")
	parser.add_option("-c", "--centerfreq", type="eng_float", default=867.5e6,
						help="set center receive frequency to MHz [default=%default]. Set to center of 800MHz band for best results")
	parser.add_option("-g", "--gain", type="int", default=None,
						help="set RF gain", metavar="dB")
	parser.add_option("-b", "--bandwidth", type="eng_float", default=3e6,
						help="set bandwidth of DBS RX frond end [default=%default]")
	parser.add_option("-F", "--filename", type="string", default=None,
						help="read data from filename rather than USRP")
	parser.add_option("-t", "--tgfile", type="string", default="sf_talkgroups.csv",
						help="read in CSV-formatted talkgroup list for pretty printing of talkgroup names")
	parser.add_option("-C", "--chanlistfile", type="string", default="motochan14.csv",
						help="read in list of Motorola channel frequencies (improves accuracy of frequency decoding) [default=%default]")
	parser.add_option("-e", "--allowdupes", action="store_false", default=True,
						help="do not eliminate duplicate records (produces lots of noise)")
	parser.add_option("-E", "--error", type="eng_float", default=0,
						help="enter an offset error to compensate for USRP clock inaccuracy")
	parser.add_option("-u", "--audio", action="store_true", default=False,
						help="output audio on speaker")
	parser.add_option("-m", "--monitor", type="int", default=0,
						help="monitor a specific talkgroup")
	parser.add_option("-v", "--volume", type="eng_float", default=0.2,
						help="set volume gain for audio output [default=%default]")
	parser.add_option("-s", "--squelch", type="eng_float", default=28,
						help="set audio squelch level (default=%default, play with it)")
	parser.add_option("-s", "--subdev", type="string",
						help="UHD subdev spec", default=None)
	parser.add_option("-A", "--antenna", type="string", default=None,
					help="select Rx Antenna where appropriate")
	parser.add_option("-r", "--rate", type="eng_float", default=64e6/18,
						help="set sample rate [default=%default]")
	parser.add_option("-a", "--addr", type="string", default="",
						help="address options to pass to UHD")

	#receive_path.add_options(parser, expert_grp)

	(options, args) = parser.parse_args ()

	if len(args) != 0:
		parser.print_help(sys.stderr)
		sys.exit(1)

	if options.tgfile is not None:
		tgreader=csv.DictReader(open(options.tgfile), quotechar='"')
		shorttglist = {"0": 0}
		longtglist = {"0": 0}
		for record in tgreader:
#			print record['tgnum']
			shorttglist[record['tgnum']] = record['shortname']
			longtglist[record['tgnum']] = record['longname']
	else:
		shorttglist = None
		longtglist = None

	if options.chanlistfile is not None:
		clreader=csv.DictReader(open(options.chanlistfile), quotechar='"')
		chanlist={"0": 0}
		for record in clreader:
			chanlist[record['channel']] = record['frequency']
	else:
		chanlist = None

	# build the graph
	queue = gr.msg_queue(10)
	tb = my_top_block(options, queue)
	runner = top_block_runner(tb)

	global dupes
	dupes = {0: 0}
	global lastmsg
	lastmsg = {"command": 0x0000, "address": 0x0000}
	global lastlastmsg
	lastlastmsg = lastmsg

	currentoffset = 0

	updaterate = 10

	#tb.setvolume(options.volume)
	#tb.mute()

	try:
		while 1:
			if not queue.empty_p():
				msg = queue.delete_head() # Blocking read
				sentence = msg.to_string()
				s = parse(sentence, shorttglist, longtglist, chanlist, options.allowdupes)
				if s is not None: 
					print s
				
				if options.audio:
					[newfreq, newaddr] = parsefreq(sentence, chanlist)

					if newfreq == currentoffset and newaddr != (options.monitor & 0xFFF0):
						tb.mute()
					if newaddr == (options.monitor & 0xFFF0): #the mask is to allow listening to all "flags" within a talkgroup: emergency, broadcast, etc.
                                            tb.unmute(options.volume)
                                            if newfreq is not None and newfreq != currentoffset:
                                                print "Changing freq to %f" % newfreq
                                                currentoffset = newfreq
                                                tb.tuneoffset(newfreq + options.offset, options.centerfreq)

			elif runner.done:
				break
			else:
				time.sleep(1.0/updaterate)

#		tb.run()

	except KeyboardInterrupt:
		tb.stop()
		runner = None

if __name__ == '__main__':
	main()


