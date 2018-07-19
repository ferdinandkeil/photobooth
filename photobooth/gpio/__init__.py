#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Photobooth - a flexible photo booth software
# Copyright (C) 2018  Balthasar Reuter <photobooth at re - web dot eu>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

import logging

from .. import StateMachine
from ..Threading import Workers


class Gpio:

    def __init__(self, config, comm):

        super().__init__()

        self._comm = comm
        self._gpio = None

        self._is_trigger = False
        self._is_enabled = config.getBool('Gpio', 'enable')

        self.initGpio(config)

    def initGpio(self, config):

        if self._is_enabled:
            self._gpio = Entities()

            lamp_pin = config.getInt('Gpio', 'lamp_pin')
            flash_pin = config.getInt('Gpio', 'flash_pin')
            trigger_pin = config.getInt('Gpio', 'trigger_pin')
            exit_pin = config.getInt('Gpio', 'exit_pin')
            startover_pin = config.getInt('Gpio', 'startover_pin')
            startover_led = config.getInt('Gpio', 'startover_led')
            print_pin = config.getInt('Gpio', 'print_pin')
            print_led = config.getInt('Gpio', 'print_led')

            logging.info(('GPIO enabled (lamp_pin=%d, trigger_pin=%d, '
                         'exit_pin=%d)'), lamp_pin, trigger_pin, exit_pin)

            self._gpio.setButton(trigger_pin, self.trigger)
            self._gpio.setButton(exit_pin, self.exit)
            self._gpio.setButton(startover_pin, self.startover)
            self._gpio.setButton(print_pin, self.print)
            self._lamp = self._gpio.setLamp(lamp_pin)
            self._flash = self._gpio.setFlash(flash_pin)
            self._startover = self._gpio.setLamp(startover_led)
            self._print = self._gpio.setLamp(print_led)
        else:
            logging.info('GPIO disabled')

    def run(self):

        for state in self._comm.iter(Workers.GPIO):
            self.handleState(state)

        return True

    def handleState(self, state):

        if isinstance(state, StateMachine.IdleState):
            self.showIdle()
        elif isinstance(state, StateMachine.GreeterState):
            self.showGreeter()
        elif isinstance(state, StateMachine.CountdownState):
            self.showCountdown()
        elif isinstance(state, StateMachine.CaptureState):
            self.showCapture()
        elif isinstance(state, StateMachine.AssembleState):
            self.showAssemble()
        elif isinstance(state, StateMachine.ReviewState):
            self.showReview()
        elif isinstance(state, StateMachine.PostprocessState):
            self.showPostprocess()
        elif isinstance(state, StateMachine.PrintingState):
            self.showPrinting()
        elif isinstance(state, StateMachine.TeardownState):
            self.teardown(state)

    def teardown(self, state):

        self._gpio.flashOff(self._flash)

    def enableTrigger(self):

        if self._is_enabled:
            self._is_trigger = True
            self._gpio.lampOn(self._lamp)

    def disableTrigger(self):

        if self._is_enabled:
            self._is_trigger = False
            self._gpio.lampOff(self._lamp)

    def trigger(self):

        if self._is_trigger:
            self.disableTrigger()
            self._comm.send(Workers.MASTER, StateMachine.GpioEvent('trigger'))

    def print(self):

        self._comm.send(Workers.MASTER, StateMachine.GpioEvent('print'))

    def startover(self):

        self._comm.send(Workers.MASTER, StateMachine.GpioEvent('idle'))

    def exit(self):

        self._comm.send(
            Workers.MASTER,
            StateMachine.TeardownEvent(StateMachine.TeardownEvent.WELCOME))

    def showIdle(self):

        self.enableTrigger()
        self.showPrinting()
        self._gpio.flashLow(self._flash)

    def showGreeter(self):

        self.disableTrigger()

    def showCountdown(self):

        self._gpio.flashLow(self._flash)

    def showCapture(self):

        self._gpio.flashFlash(self._flash)

    def showAssemble(self):

        self._gpio.flashLow(self._flash)

    def showReview(self):

        pass

    def showPostprocess(self):

        self._gpio.lampOn(self._startover)
        self._gpio.lampOn(self._print)

    def showPrinting(self):

        self._gpio.lampOff(self._startover)
        self._gpio.lampOff(self._print)


class Entities:

    def __init__(self):

        super().__init__()

        import gpiozero
        self.LED = gpiozero.LED
        self.PWMLED = gpiozero.PWMLED
        self.Button = gpiozero.Button

        import subprocess
        self.sp = subprocess

        self._buttons = []
        self._lamps = []

    def setButton(self, bcm_pin, handler):

        self._buttons.append(self.Button(bcm_pin))
        self._buttons[-1].when_pressed = handler

    def setLamp(self, bcm_pin):

        self._lamps.append(self.LED(bcm_pin))
        return len(self._lamps) - 1

    def lampOn(self, index):

        self._lamps[index].on()

    def lampOff(self, index):

        self._lamps[index].off()

    def lampToggle(self, index):

        self._lamps[index].toggle()

    def setFlash(self, bcm_pin):

        self.sp.run(['gpio', '-g', 'mode', str(bcm_pin), 'pwm'])
        self.sp.run(['gpio', 'pwm-ms'])
        self.sp.run(['gpio', 'pwmc', '64'])
        self.sp.run(['gpio', 'pwmr', '1023'])
        self.sp.run(['gpio', '-g', 'pwm', str(bcm_pin), '0'])
        return bcm_pin

    def flashFlash(self, bcm_pin):

        self.sp.run(['gpio', '-g', 'pwm', str(bcm_pin), '1023'])

    def flashLow(self, bcm_pin):

        self.sp.run(['gpio', '-g', 'pwm', str(bcm_pin), '200'])

    def flashOff(self, bcm_pin):

        self.sp.run(['gpio', '-g', 'pwm', str(bcm_pin), '0'])
