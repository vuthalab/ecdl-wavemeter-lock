from typing import Literal


class RigolDG1000zCommands:
    def __init__(self): ...

    def get_state(self, channel: Literal[1, 2]):
        return f":OUTP{channel}?"

    def set_state(self, channel: Literal[1, 2], state: bool):
        if state:
            return f":OUTP{channel} ON"
        else:
            return f":OUTP{channel} OFF"

    def get_function(self, channel: Literal[1, 2]):
        return f":SOUR{channel}:FUNC?"

    def set_function(self, channel: Literal[1, 2], function_name: str):
        return f":SOUR{channel}:FUNC {function_name}"

    def get_frequency(self, channel: Literal[1, 2]):
        return f":SOUR{channel}:FREQ?"

    def set_frequency(self, channel: Literal[1, 2], frequency: float):
        return f":SOUR{channel}:FREQ {frequency}"

    def get_amplitude(self, channel: Literal[1, 2]):
        return f":SOUR{channel}:VOLT?"

    def set_amplitude(self, channel: Literal[1, 2], amplitude: float):
        return f":SOUR{channel}:VOLT {amplitude}"

    def get_offset_voltage(self, channel: Literal[1, 2]):
        # :SOUR:VOLT:OFFS? does not work. Bug of Rigol func. gen.
        return f":SOUR{channel}:APPLY?"

    def set_offset_voltage(self, channel: Literal[1, 2], offset: float):
        return f":SOUR{channel}:VOLT:OFFS {offset}"


class RigolDG1000z:
    def __init__(self, address: str, protocol: Literal["Ethernet", "USB"] = "Ethernet"):
        if protocol == "Ethernet":
            import vxi11

            address = f"TCPIP0::{address}::INSTR"
            self._inst = vxi11.Instrument(address)
            name = "Rigol Technologies,DG1"
            if self._inst.ask("*IDN?")[0:len(name)] != name:
                raise ValueError("Address does not link to a Rigol series DG1000z device.")
        elif protocol == "USB":
            import pyvisa

            rm = pyvisa.ResourceManager()
            self._inst = rm.open_resource(address)
        else:
            raise NotImplementedError()
        self._protocol = protocol
        self._commands = RigolDG1000zCommands()

    def ask(self, command: str):
        if self._protocol == "Ethernet":
            return self._inst.ask(command)
        elif self._protocol == "USB":
            return self._inst.query(command)[:-1]
        else:
            raise NotImplementedError()
    
    def write(self, command: str):
        if self._protocol == "Ethernet":
            self._inst.write(command)
        elif self._protocol == "USB":
            self._inst.write(command)
        else:
            raise NotImplementedError()

    def get_state(self, channel: Literal[1, 2]) -> bool:
        return self.ask(self._commands.get_state(channel)) == "ON"

    def set_state(self, channel: Literal[1, 2], state: bool):
        self.write(self._commands.set_state(channel, state))

    def get_function(self, channel: Literal[1, 2]) -> str:
        return self.ask(self._commands.get_function(channel))

    def set_function(self, channel: Literal[1, 2], function: str):
        self.write(self._commands.set_function(channel, function))

    def get_frequency(self, channel: Literal[1, 2]) -> float:
        return float(self.ask(self._commands.get_frequency(channel)))

    def set_frequency(self, channel: Literal[1, 2], frequency: float):
        self.write(self._commands.set_frequency(channel, frequency))

    def get_amplitude(self, channel: Literal[1, 2]) -> float:
        return float(self.ask(self._commands.get_amplitude(channel)))

    def set_amplitude(self, channel: Literal[1, 2], amplitude: float):
        self.write(self._commands.set_amplitude(channel, amplitude))

    def get_offset_voltage(self, channel: Literal[1, 2]) -> float:
        all_info = self.ask(self._commands.get_offset_voltage(channel))
        return float(all_info[:-1].split(",")[-1])

    def set_offset_voltage(self, channel: Literal[1, 2], offset_voltage: float):
        self.write(self._commands.set_offset_voltage(channel, offset_voltage))
