# ***************************************************************************
# *   Copyright (c) 2021 shadowbane1000 <tyler@colberts.us>               *
# *                                                                         *
# *   This file is part of the FreeCAD CAx development system.              *
# *                                                                         *
# *   This program is free software; you can redistribute it and/or modify  *
# *   it under the terms of the GNU Lesser General Public License (LGPL)    *
# *   as published by the Free Software Foundation; either version 2 of     *
# *   the License, or (at your option) any later version.                   *
# *   for detail see the LICENCE text file.                                 *
# *                                                                         *
# *   FreeCAD is distributed in the hope that it will be useful,            *
# *   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
# *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
# *   GNU Lesser General Public License for more details.                   *
# *                                                                         *
# *   You should have received a copy of the GNU Library General Public     *
# *   License along with FreeCAD; if not, write to the Free Software        *
# *   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  *
# *   USA                                                                   *
# *                                                                         *
# ***************************************************************************

from __future__ import print_function

import argparse
import shlex
#import PathLog

class PostArgs():
    '''
    Class to manage arguments for post processor scripts.  In your post
    processor script, the getArgs method will be passed a PostArgs object.
    Note that the --, or the --no- get added to the argument based on
    what the type of argument is, and what the default value is.
    
    to add a true/false argument called 'my-argument' that defaults to True
    call this:
      parser.add_argument('my-argument', True, 'Enable the my-argument feature')
    
    You can also default to false:
      parser.add_argument('my-argument', False, 'Enable the my-argument feature')
    
    Arguments can also be values, rather than True/False like this:
      parser.add_argument('my-argument', 10, 'Change the my-argument count (default 10)')
    
    You can remove arguments created by the base postprocessor.py like this:
      parser.remove_argument('my-argument')
    
    If your postprocessor would be better of with a different default value
    for an argument created by postprocessor.py, change it like this:
      parser.set_default('my-argument', True)
      
    Once you have the arguments, you can access them this way:
      args.my_argument
    '''
    def __init__(self, name):
        self._name = name
        self._arguments = {}

    def add_argument(self, argument_name, default, help):
        '''
        Adds an argument to the list of arguments for this post processor.
        Parameters:
          argument_name - The name of the argument.  a '--' or a '--no-'
                          should be prepended when passed on the command
                          line.
          default - The value used if the caller doesn't specify the option.
                    If this is True or False, the option is considered a 
                    boolean flag, that can be specified or not.  If the
                    default is any other value, the option will one that
                    requires a value (string or number).
          help - The help text for the option.  If the option is a boolean
                 flag, the help text should be written in the 'True' sense
                 regardless of the default value you use. This is in case
                 someone derives from your post processor and changes the
                 default value.
        '''
        self._arguments[argument_name] = (default,help)
       
    def remove_argument(self, argument_name):
        '''
        Removes an argument from the list of arguments that are allowed
        for this post processor.  This is useful if the default 
        postprocessor.py creates an argument that doesn't make sense
        for a particular post processor.
        Parameters:
          argument_name - The name the argument was created with
        '''
        del(self._arguments[argument_name])

    def set_default(self, argument_name, default):
        '''
        Change the default value that was previously configured for this
        argument.  This is useful if postprocessor.py created an argument
        that you want to keep, but a different default value would be 
        useful for your post processor.
        '''
        self._arguments[argument_name][0] = default

    def processArguments(self, argstring):
        '''
        This method is called by postprocessor.py to actually handle the
        arguments.  You would only need to call this if you are overriding
        ObjectPost.processArguments().
        '''
        parser = argparse.ArgumentParser(prog=self._name)
        for arg in self._arguments:
            if type(self._arguments[arg][0]) == type(True):
                if self._arguments[arg][0]:
                    parser.add_argument('--no-' + arg, action='store_const', const=False, dest=arg.replace('-','_'), default=self._arguments[arg][0], help=self._arguments[arg][1])
                else:
                    parser.add_argument('--' + arg, action='store_const', const=True, dest=arg.replace('-','_'), default=self._arguments[arg][0], help=self._arguments[arg][1])
            else:
                parser.add_argument('--' + arg, default=self._arguments[arg][0], help=self._arguments[arg][1]) 

        
        PathLog.debug(argstring)

        try:
            args = parser.parse_args(shlex.split(argstring))
        except Exception as e:
            print(e)
            return None

        PathLog.debug(args)
        return args
3+
