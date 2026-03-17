import pigpio
import time

# ======================
# KONFIGURACJA PINÓW
# ======================

PIN_BUZZER = 18
PIN_BUTTON = 23
PIN_LED = 17

API_INTERVAL = 30
BEEP_INTERVAL = 0.35
PAUSE_INTERVAL = 1.2
BEEPS_IN_GROUP = 3


# ======================
# HARDWARE CONTROLLER
# ======================

class HardwareController:

    def __init__(self):

        self.pi = pigpio.pi()

        if not self.pi.connected:
            raise RuntimeError("pigpio daemon not running")

        # GPIO konfiguracja
        self.pi.set_mode(PIN_BUZZER, pigpio.OUTPUT)
        self.pi.set_mode(PIN_LED, pigpio.OUTPUT)

        self.pi.set_mode(PIN_BUTTON, pigpio.INPUT)
        self.pi.set_pull_up_down(PIN_BUTTON, pigpio.PUD_UP)

        # stan buzzera
        self.last_beep = time.time()
        self.beep_state = False
        self.beep_count = 0

        # debounce przycisku
        self.last_button_state = 1
        self.last_button_time = 0
        self.debounce_time = 0.05  # 50 ms

    # ----------------------
    # BUZZER
    # ----------------------

    def start_buzzer(self):
        """Stały ton alarmu"""
        self.pi.hardware_PWM(PIN_BUZZER, 2800, 500000)

    def stop_buzzer(self):
        self.pi.hardware_PWM(PIN_BUZZER, 0, 0)

    def update_alarm_sound(self, enabled):

        if not enabled:
            # reset sekwencji gdy alarm wyłączony
            self.stop_buzzer()
            self.beep_count = 0
            self.beep_state = False
            return

        now = time.time()

        interval = BEEP_INTERVAL

        # po serii bipów robimy pauzę
        if self.beep_count >= BEEPS_IN_GROUP:
            interval = PAUSE_INTERVAL

        if now - self.last_beep > interval:

            self.last_beep = now
            self.beep_state = not self.beep_state

            if self.beep_state:
                self.start_buzzer()
            else:
                self.stop_buzzer()
                self.beep_count += 1

                if self.beep_count >= BEEPS_IN_GROUP:
                    self.beep_count = 0

    # ----------------------
    # LED
    # ----------------------

    def led_on(self):
        self.pi.write(PIN_LED, 1)

    def led_off(self):
        self.pi.write(PIN_LED, 0)

    def led_flash(self, duration=0.5):
        self.led_on()
        time.sleep(duration)
        self.led_off()
    # ----------------------

    def button_pressed(self):

        now = time.time()
        state = self.pi.read(PIN_BUTTON)

        # zmiana stanu przycisku
        if state != self.last_button_state:
            self.last_button_time = now
            self.last_button_state = state

        # jeśli stan stabilny przez debounce_time
        if (now - self.last_button_time) > self.debounce_time:
            if state == 0:  # przycisk wciśnięty
                return True

        return False

    def cleanup(self):
        self.stop_buzzer()
        self.pi.stop()


# ======================
# MOCK API
# ======================

class MockFurnaceAPI:

    def __init__(self):
        self.state = False

    def get_alarm_state(self):
        self.state = not self.state
        return self.state


# ======================
# STATE MACHINE
# ======================

class AlarmStateMachine:

    STATE_OK = "OK"
    STATE_ALARM = "ALARM"

    def __init__(self, hardware, api):

        self.hardware = hardware
        self.api = api
        self.state = self.STATE_OK

    def poll_api(self):

        alarm = self.api.get_alarm_state()

        if alarm:

            print("ALARM detected")

            self.state = self.STATE_ALARM
            self.hardware.led_on()

        else:

            print("System OK")

            if self.state != self.STATE_ALARM:
                self.hardware.led_flash(0.5)

    def check_button(self):

        if self.state == self.STATE_ALARM and self.hardware.button_pressed():

            print("Alarm acknowledged")

            self.state = self.STATE_OK
            self.hardware.stop_buzzer()
            self.hardware.led_off()


# ======================
# MAIN LOOP + WATCHDOG
# ======================


def main():

    hardware = HardwareController()
    api = MockFurnaceAPI()

    state_machine = AlarmStateMachine(hardware, api)

    last_api_call = 0

    # watchdog – wykrywa zablokowanie pętli
    last_loop_time = time.time()
    WATCHDOG_TIMEOUT = 5  # sekundy

    try:

        while True:

            now = time.time()

            # --- WATCHDOG ---
            if now - last_loop_time > WATCHDOG_TIMEOUT:
                print("WATCHDOG: loop delay detected – resetting buzzer")
                hardware.stop_buzzer()
                last_loop_time = now

            last_loop_time = now

            # --- API polling ---
            if now - last_api_call > API_INTERVAL:

                last_api_call = now
                state_machine.poll_api()

            # --- przycisk ---
            state_machine.check_button()

            # --- alarm ---
            hardware.update_alarm_sound(
                state_machine.state == AlarmStateMachine.STATE_ALARM
            )

            time.sleep(0.05)

    except KeyboardInterrupt:

        print("Shutting down...")

    finally:

        hardware.cleanup()


if __name__ == "__main__":
    main()
