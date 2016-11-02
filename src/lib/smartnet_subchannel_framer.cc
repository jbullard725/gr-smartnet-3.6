//smartnet_subchannel_framer.cc
/* -*- c++ -*- */
/*
 * Copyright 2004 Free Software Foundation, Inc.
 *
 * This file is part of GNU Radio
 *
 * GNU Radio is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2, or (at your option)
 * any later version.
 *
 * GNU Radio is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with GNU Radio; see the file COPYING.  If not, write to
 * the Free Software Foundation, Inc., 51 Franklin Street,
 * Boston, MA 02110-1301, USA.
 */

/*
 * config.h is generated by configure.  It contains the results
 * of probing for features, options etc.  It should be the first
 * file included in your .cc file.
 */
#ifdef HAVE_CONFIG_H
#include "config.h"
#endif

#include <smartnet_subchannel_framer.h>
#include <gnuradio/io_signature.h>
#include <sstream>
#include <stdio.h>

/*
 * Create a new instance of smartnet_sync and return
 * a boost shared_ptr.  This is effectively the public constructor.
 */
smartnet_subchannel_framer_sptr smartnet_make_subchannel_framer()
{
  return smartnet_subchannel_framer_sptr (new smartnet_subchannel_framer ());
}

/*
 * Specify constraints on number of input and output streams.
 * This info is used to construct the input and output signatures
 * (2nd & 3rd args to gr::block's constructor).  The input and
 * output signatures are used by the runtime system to
 * check that a valid number and type of inputs and outputs
 * are connected to this block.  In this case, we accept
 * only 1 input and 1 output.
 */
static const int MIN_IN = 1;    // mininum number of input streams
static const int MAX_IN = 1;    // maximum number of input streams
static const int MIN_OUT = 1;   // minimum number of output streams
static const int MAX_OUT = 1;   // maximum number of output streams

/*
 * The private constructor
 */
smartnet_subchannel_framer::smartnet_subchannel_framer ()
  : gr::sync_block ("subchannel_framer",
                   gr::io_signature::make (MIN_IN, MAX_IN, sizeof (char)),
                   gr::io_signature::make (MIN_OUT, MAX_OUT, sizeof (char)))
{
  // nothing else required in this example
	set_output_multiple(42);
}

/*
 * Our virtual destructor.
 */
smartnet_subchannel_framer::~smartnet_subchannel_framer ()
{
  // nothing else required in this example
}

int
smartnet_subchannel_framer::work (int noutput_items,
                        gr_vector_const_void_star &input_items,
                        gr_vector_void_star &output_items)
{
  const char *in = (const char *) input_items[0];
  char *out = (char *) output_items[0];

	//iterate over all output items
	//if you get one with a correlator trigger, if there's 21 more left in the queue, if the 21st one on also has a trigger, then it's good! otherwise clear it cause it's a false flag

	for(int i=0; i < noutput_items; i++) {
		if(in[i] & 0x02) {
			//if(noutput_items-i >= 21) {
				//if(in[i+21] & 0x02) {
					out[i] = in[i];
					printf("Subchannel frame data: ");
					for(int q = 0; q < 42; q++) {
						if(in[i+q-5] & 0x01) printf("1");
						else printf("0");
					}
					printf("\n");
//				}
			//	else out[i] = in[i] & 0x01;
			//} else return i; //weren't enough to validate it, so go back for more
		} else out[i] = in[i];

	}

  // Tell runtime system how many output items we produced.
  return noutput_items;
}

