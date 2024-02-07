# SPDX-License-Identifier: BSD-2-Clause

from abc        import abstractmethod
from typing     import Literal, Optional

from ....build  import Attrs, Clock, Subsignal, TemplatedPlatform
from ....hdl    import (
	ClockDomain, ClockSignal, Const, Instance, Module, Record, Signal
)
from ....lib.io import Pin

__all__ = (
	'ECP5Platform',
)

class ECP5Platform(TemplatedPlatform):
	'''
	.. rubric:: Trellis toolchain

	Required tools:
		* ``yosys``
		* ``nextpnr-ecp5``
		* ``ecppack``

	The environment is populated by running the script specified in the environment variable
	``TORII_ENV_TRELLIS``, if present.

	Available overrides:
		* ``verbose``: enables logging of informational messages to standard error.
		* ``read_verilog_opts``: adds options for ``read_verilog`` Yosys command.
		* ``synth_opts``: adds options for ``synth_ecp5`` Yosys command.
		* ``script_after_read``: inserts commands after ``read_rtlil`` in Yosys script.
		* ``script_after_synth``: inserts commands after ``synth_ecp5`` in Yosys script.
		* ``yosys_opts``: adds extra options for ``yosys``.
		* ``nextpnr_opts``: adds extra options for ``nextpnr-ecp5``.
		* ``ecppack_opts``: adds extra options for ``ecppack``.
		* ``add_preferences``: inserts commands at the end of the LPF file.

	Build products:
		* ``{{name}}.rpt``: Yosys log.
		* ``{{name}}.json``: synthesized RTL.
		* ``{{name}}.tim``: nextpnr log.
		* ``{{name}}.config``: ASCII bitstream.
		* ``{{name}}.bit``: binary bitstream.
		* ``{{name}}.svf``: JTAG programming vector.

	.. rubric:: Diamond toolchain

	Required tools:
		* ``pnmainc``
		* ``ddtcmd``

	The environment is populated by running the script specified in the environment variable
	``TORII_ENV_DIAMOND``, if present. On Linux, diamond_env as provided by Diamond
	itself is a good candidate. On Windows, the following script (named ``diamond_env.bat``,
	for instance) is known to work::

		@echo off
		set PATH = C:\\lscc\\diamond\\%DIAMOND_VERSION%\\bin\\nt64;%PATH%

	Available overrides:
		* ``script_project``: inserts commands before ``prj_project save`` in Tcl script.
		* ``script_after_export``: inserts commands after ``prj_run Export`` in Tcl script.
		* ``add_preferences``: inserts commands at the end of the LPF file.
		* ``add_constraints``: inserts commands at the end of the XDC file.

	Build products:
		* ``{{name}}_impl/{{name}}_impl.htm``: consolidated log.
		* ``{{name}}.bit``: binary bitstream.
		* ``{{name}}.svf``: JTAG programming vector.

	'''

	toolchain = None # selected when creating platform

	@property
	@abstractmethod
	def device(self) -> str:
		raise NotImplementedError('Platform must implement this property')

	@property
	@abstractmethod
	def package(self) -> str:
		raise NotImplementedError('Platform must implement this property')

	@property
	@abstractmethod
	def speed(self) -> str:
		raise NotImplementedError('Platform must implement this property')

	grade   = 'C' # [C]ommercial, [I]ndustrial

	# Trellis templates

	_nextpnr_device_options = {
		'LFE5U-12F':    '--12k',
		'LFE5U-25F':    '--25k',
		'LFE5U-45F':    '--45k',
		'LFE5U-85F':    '--85k',
		'LFE5UM-25F':   '--um-25k',
		'LFE5UM-45F':   '--um-45k',
		'LFE5UM-85F':   '--um-85k',
		'LFE5UM5G-25F': '--um5g-25k',
		'LFE5UM5G-45F': '--um5g-45k',
		'LFE5UM5G-85F': '--um5g-85k',
	}
	_nextpnr_package_options = {
		'BG256': 'caBGA256',
		'MG285': 'csfBGA285',
		'BG381': 'caBGA381',
		'BG554': 'caBGA554',
		'BG756': 'caBGA756',
	}

	_trellis_required_tools = [
		'yosys',
		'nextpnr-ecp5',
		'ecppack'
	]
	_trellis_file_templates = {
		**TemplatedPlatform.build_script_templates,
		'{{name}}.il': r'''
			# {{autogenerated}}
			{{emit_rtlil()}}
		''',
		'{{name}}.debug.v': r'''
			/* {{autogenerated}} */
			{{emit_debug_verilog()}}
		''',
		'{{name}}.ys': r'''
			# {{autogenerated}}
			{% for file in platform.iter_files(".v") -%}
				read_verilog {{get_override("read_verilog_opts")|options}} {{file}}
			{% endfor %}
			{% for file in platform.iter_files(".sv") -%}
				read_verilog -sv {{get_override("read_verilog_opts")|options}} {{file}}
			{% endfor %}
			{% for file in platform.iter_files(".il") -%}
				read_rtlil {{file}}
			{% endfor %}
			read_rtlil {{name}}.il
			delete w:$verilog_initial_trigger
			{{get_override("script_after_read")|default("# (script_after_read placeholder)")}}
			synth_ecp5 {{get_override("synth_opts")|options}} -top {{name}}
			{{get_override("script_after_synth")|default("# (script_after_synth placeholder)")}}
			write_json {{name}}.json
		''',
		'{{name}}.lpf': r'''
			# {{autogenerated}}
			BLOCK ASYNCPATHS;
			BLOCK RESETPATHS;
			{% for port_name, pin_name, attrs in platform.iter_port_constraints_bits() -%}
				LOCATE COMP "{{port_name}}" SITE "{{pin_name}}";
				{% if attrs -%}
				IOBUF PORT "{{port_name}}"
					{%- for key, value in attrs.items() %} {{key}}={{value}}{% endfor %};
				{% endif %}
			{% endfor %}
			{% for net_signal, port_signal, frequency in platform.iter_clock_constraints() -%}
				{% if port_signal is not none -%}
					FREQUENCY PORT "{{port_signal.name}}" {{frequency}} HZ;
				{% else -%}
					FREQUENCY NET "{{net_signal|hierarchy(".")}}" {{frequency}} HZ;
				{% endif %}
			{% endfor %}
			{{get_override("add_preferences")|default("# (add_preferences placeholder)")}}
		'''
	}
	_trellis_command_templates = [
		r'''
		{{invoke_tool("yosys")}}
			{{quiet("-q")}}
			{{get_override("yosys_opts")|options}}
			-l {{name}}.rpt
			{{name}}.ys
		''',
		r'''
		{{invoke_tool("nextpnr-ecp5")}}
			{{quiet("--quiet")}}
			{{get_override("nextpnr_opts")|options}}
			--log {{name}}.tim
			{{platform._nextpnr_device_options[platform.device]}}
			--package {{platform._nextpnr_package_options[platform.package]|upper}}
			--speed {{platform.speed}}
			--json {{name}}.json
			--lpf {{name}}.lpf
			--textcfg {{name}}.config
		''',
		r'''
		{{invoke_tool("ecppack")}}
			{{verbose("--verbose")}}
			{{get_override("ecppack_opts")|options}}
			--input {{name}}.config
			--bit {{name}}.bit
			--svf {{name}}.svf
		'''
	]

	# Diamond templates

	_diamond_required_tools = [
		'pnmainc',
		'ddtcmd',
	]
	_diamond_file_templates = {
		**TemplatedPlatform.build_script_templates,
		'build_{{name}}.sh': r'''
			# {{autogenerated}}
			set -e{{verbose("x")}}
			if [ -z "$BASH" ] ; then exec /bin/bash "$0" "$@"; fi
			if [ -n "${{platform._toolchain_env_var}}" ]; then
				bindir=$(dirname "${{platform._toolchain_env_var}}")
				. "${{platform._toolchain_env_var}}"
			fi
			{{emit_commands("sh")}}
		''',
		'{{name}}.v': r'''
			/* {{autogenerated}} */
			{{emit_verilog()}}
		''',
		'{{name}}.debug.v': r'''
			/* {{autogenerated}} */
			{{emit_debug_verilog()}}
		''',
		'{{name}}.tcl': r'''
			prj_project new -name {{name}} -impl impl -impl_dir {{name}}_impl \
				-dev {{platform.device}}-{{platform.speed}}{{platform.package}}{{platform.grade}} \
				-lpf {{name}}.lpf \
				-synthesis synplify
			{% for file in platform.iter_files(".v", ".sv", ".vhd", ".vhdl") -%}
				prj_src add {{file|tcl_escape}}
			{% endfor %}
			prj_src add {{name}}.v
			prj_impl option top {{name}}
			prj_src add {{name}}.sdc
			{{get_override("script_project")|default("# (script_project placeholder)")}}
			prj_project save
			prj_run Synthesis -impl impl
			prj_run Translate -impl impl
			prj_run Map -impl impl
			prj_run PAR -impl impl
			prj_run Export -impl impl -task Bitgen
			{{get_override("script_after_export")|default("# (script_after_export placeholder)")}}
		''',
		'{{name}}.lpf': r'''
			# {{autogenerated}}
			BLOCK ASYNCPATHS;
			BLOCK RESETPATHS;
			{% for port_name, pin_name, attrs in platform.iter_port_constraints_bits() -%}
				LOCATE COMP "{{port_name}}" SITE "{{pin_name}}";
				{% if attrs -%}
				IOBUF PORT "{{port_name}}"
					{%- for key, value in attrs.items() %} {{key}}={{value}}{% endfor %};
				{% endif %}
			{% endfor %}
			{{get_override("add_preferences")|default("# (add_preferences placeholder)")}}
		''',
		'{{name}}.sdc': r'''
			{% for net_signal, port_signal, frequency in platform.iter_clock_constraints() -%}
				{% if port_signal is not none -%}
					create_clock -name {{port_signal.name|tcl_escape}} -period {{1000000000/frequency}} [get_ports {{port_signal.name|tcl_escape}}]
				{% else -%}
					create_clock -name {{net_signal.name|tcl_escape}} -period {{1000000000/frequency}} [get_nets {{net_signal|hierarchy("/")|tcl_escape}}]
				{% endif %}
			{% endfor %}
			{{get_override("add_constraints")|default("# (add_constraints placeholder)")}}
		''' # noqa: E501
	}
	_diamond_command_templates = [
		# These don't have any usable command-line option overrides.
		r'''
		{{invoke_tool("pnmainc")}}
			{{name}}.tcl
		''',
		r'''
		{{invoke_tool("ddtcmd")}}
			-oft -bit
			-if {{name}}_impl/{{name}}_impl.bit -of {{name}}.bit
		''',
		r'''
		{{invoke_tool("ddtcmd")}}
			-oft -svfsingle -revd -op "Fast Program"
			-if {{name}}_impl/{{name}}_impl.bit -of {{name}}.svf
		''',
	]

	# Common logic

	def __init__(
		self, *, toolchain: Literal['Trellis', 'Diamond'] = 'Trellis'
	) -> None:
		super().__init__()

		if self.toolchain not in ('Trellis', 'Diamond'):
			raise ValueError(f'Unknown toolchain \'{self.toolchain}\', must be either \'Trellis\', or \'Diamond\'')

		self.toolchain = toolchain

	@property
	def required_tools(self) -> list[str]:
		if self.toolchain not in ('Trellis', 'Diamond'):
			raise ValueError(f'Unknown toolchain \'{self.toolchain}\', must be either \'Trellis\', or \'Diamond\'')

		if self.toolchain == 'Trellis':
			return self._trellis_required_tools
		if self.toolchain == 'Diamond':
			return self._diamond_required_tools

	@property
	def file_templates(self) -> dict[str, str]:
		if self.toolchain not in ('Trellis', 'Diamond'):
			raise ValueError(f'Unknown toolchain \'{self.toolchain}\', must be either \'Trellis\', or \'Diamond\'')

		if self.toolchain == 'Trellis':
			return self._trellis_file_templates
		if self.toolchain == 'Diamond':
			return self._diamond_file_templates

	@property
	def command_templates(self) -> list[str]:
		if self.toolchain not in ('Trellis', 'Diamond'):
			raise ValueError(f'Unknown toolchain \'{self.toolchain}\', must be either \'Trellis\', or \'Diamond\'')

		if self.toolchain == 'Trellis':
			return self._trellis_command_templates
		if self.toolchain == 'Diamond':
			return self._diamond_command_templates

	@property
	def default_clk_constraint(self) -> Clock:
		if self.default_clk == 'OSCG':
			return Clock(310e6 / self.oscg_div)
		return super().default_clk_constraint

	def create_missing_domain(self, name: str) -> Module:
		# Lattice ECP5 devices have two global set/reset signals: PUR, which is driven at startup
		# by the configuration logic and unconditionally resets every storage element, and GSR,
		# which is driven by user logic and each storage element may be configured as affected or
		# unaffected by GSR. PUR is purely asynchronous, so even though it is a low-skew global
		# network, its de-assertion may violate a setup/hold constraint with relation to a user
		# clock. To avoid this, a GSR/SGSR instance should be driven synchronized to user clock.
		if name == 'sync' and self.default_clk is not None:
			m = Module()
			if self.default_clk == 'OSCG':
				if not hasattr(self, 'oscg_div'):
					raise ValueError('OSCG divider (oscg_div) must be an integer between 2 and 128')
				if not isinstance(self.oscg_div, int) or self.oscg_div < 2 or self.oscg_div > 128:
					raise ValueError(
						f'OSCG divider (oscg_div) must be an integer between 2 and 128, not {self.oscg_div!r}'
					)
				clk_i = Signal()
				m.submodules += Instance('OSCG', p_DIV = self.oscg_div, o_OSC = clk_i)
			else:
				clk_i = self.request(self.default_clk).i
			if self.default_rst is not None:
				rst_i = self.request(self.default_rst).i
			else:
				rst_i = Const(0)

			gsr0 = Signal()
			gsr1 = Signal()
			# There is no end-of-startup signal on ECP5, but PUR is released after IOB enable, so
			# a simple reset synchronizer (with PUR as the asynchronous reset) does the job.
			m.submodules += [
				Instance('FD1S3AX', p_GSR = 'DISABLED', i_CK = clk_i, i_D = ~rst_i, o_Q = gsr0),
				Instance('FD1S3AX', p_GSR = 'DISABLED', i_CK = clk_i, i_D = gsr0,   o_Q = gsr1),
				# Although we already synchronize the reset input to user clock, SGSR has dedicated
				# clock routing to the center of the FPGA; use that just in case it turns out to be
				# more reliable. (None of this is documented.)
				Instance('SGSR', i_CLK = clk_i, i_GSR = gsr1),
			]
			# GSR implicitly connects to every appropriate storage element. As such, the sync
			# domain is reset-less; domains driven by other clocks would need to have dedicated
			# reset circuitry or otherwise meet setup/hold constraints on their own.
			m.domains += ClockDomain('sync', reset_less = True)
			m.d.comb += ClockSignal('sync').eq(clk_i)
			return m

	_single_ended_io_types = [
		'HSUL12', 'LVCMOS12', 'LVCMOS15', 'LVCMOS18', 'LVCMOS25', 'LVCMOS33', 'LVTTL33',
		'SSTL135_I', 'SSTL135_II', 'SSTL15_I', 'SSTL15_II', 'SSTL18_I', 'SSTL18_II',
	]
	_differential_io_types = [
		'BLVDS25', 'BLVDS25E', 'HSUL12D', 'LVCMOS18D', 'LVCMOS25D', 'LVCMOS33D',
		'LVDS', 'LVDS25E', 'LVPECL33', 'LVPECL33E', 'LVTTL33D', 'MLVDS', 'MLVDS25E',
		'SLVS', 'SSTL135D_I', 'SSTL135D_II', 'SSTL15D_I', 'SSTL15D_II', 'SSTL18D_I',
		'SSTL18D_II', 'SUBLVDS',
	]

	def should_skip_port_component(
		self, port: Subsignal, attrs: Attrs, component: Literal['io', 'i', 'o', 'p', 'n', 'oe']
	) -> bool:
		# On ECP5, a differential IO is placed by only instantiating an IO buffer primitive at
		# the PIOA or PIOC location, which is always the non-inverting pin.
		if attrs.get('IO_TYPE', 'LVCMOS25') in self._differential_io_types and component == 'n':
			return True
		return False

	def _get_xdr_buffer(
		self, m: Module, pin: Pin, *, i_invert: bool = False, o_invert: bool = False
	) -> tuple[Optional[Signal], Optional[Signal], Optional[Signal]]:
		def get_ireg(clk: Signal, d: Signal, q: Signal) -> None:
			for bit in range(len(q)):
				m.submodules += Instance(
					'IFS1P3DX',
					i_SCLK = clk,
					i_SP = Const(1),
					i_CD = Const(0),
					i_D = d[bit],
					o_Q = q[bit]
				)

		def get_oreg(clk: Signal, d: Signal, q: Signal) -> None:
			for bit in range(len(q)):
				m.submodules += Instance(
					'OFS1P3DX',
					i_SCLK = clk,
					i_SP = Const(1),
					i_CD = Const(0),
					i_D = d[bit],
					o_Q = q[bit]
				)

		def get_oereg(clk: Signal, oe: Signal, q: Signal) -> None:
			for bit in range(len(q)):
				m.submodules += Instance(
					'OFS1P3DX',
					i_SCLK = clk,
					i_SP = Const(1),
					i_CD = Const(0),
					i_D = oe,
					o_Q = q[bit]
				)

		def get_iddr(sclk: Signal, d: Signal, q0: Signal, q1: Signal) -> None:
			for bit in range(len(d)):
				m.submodules += Instance(
					'IDDRX1F',
					i_SCLK = sclk,
					i_RST = Const(0),
					i_D = d[bit],
					o_Q0 = q0[bit],
					o_Q1 = q1[bit]
				)

		def get_iddrx2(
			sclk: Signal, eclk: Signal, d: Signal,
			q0: Signal, q1: Signal, q2: Signal, q3: Signal
		) -> None:
			for bit in range(len(d)):
				m.submodules += Instance(
					'IDDRX2F',
					i_SCLK = sclk,
					i_ECLK = eclk,
					i_RST = Const(0),
					i_D = d[bit],
					o_Q0 = q0[bit],
					o_Q1 = q1[bit],
					o_Q2 = q2[bit],
					o_Q3 = q3[bit]
				)

		def get_iddr71b(
			sclk: Signal, eclk: Signal, d: Signal,
			q0: Signal, q1: Signal, q2: Signal, q3: Signal, q4: Signal, q5: Signal, q6: Signal
		) -> None:
			for bit in range(len(d)):
				m.submodules += Instance(
					'IDDR71B',
					i_SCLK = sclk,
					i_ECLK = eclk,
					i_RST = Const(0),
					i_D = d[bit],
					o_Q0 = q0[bit],
					o_Q1 = q1[bit],
					o_Q2 = q2[bit],
					o_Q3 = q3[bit],
					o_Q4 = q4[bit],
					o_Q5 = q5[bit],
					o_Q6 = q6[bit],
				)

		def get_oddr(sclk: Signal, d0: Signal, d1: Signal, q: Signal) -> None:
			for bit in range(len(q)):
				m.submodules += Instance(
					'ODDRX1F',
					i_SCLK = sclk,
					i_RST = Const(0),
					i_D0 = d0[bit],
					i_D1 = d1[bit],
					o_Q = q[bit]
				)

		def get_oddrx2(
			sclk: Signal, eclk: Signal,
			d0: Signal, d1: Signal, d2: Signal, d3: Signal, q: Signal
		) -> None:
			for bit in range(len(q)):
				m.submodules += Instance(
					'ODDRX2F',
					i_SCLK = sclk,
					i_ECLK = eclk,
					i_RST = Const(0),
					i_D0 = d0[bit],
					i_D1 = d1[bit],
					i_D2 = d2[bit],
					i_D3 = d3[bit],
					o_Q = q[bit]
				)

		def get_oddr71b(
			sclk:  Signal, eclk:  Signal,
			d0: Signal, d1: Signal, d2: Signal, d3: Signal, d4: Signal,
			d5: Signal, d6: Signal, q: Signal
		) -> None:
			for bit in range(len(q)):
				m.submodules += Instance(
					'ODDR71B',
					i_SCLK = sclk,
					i_ECLK = eclk,
					i_RST = Const(0),
					i_D0 = d0[bit],
					i_D1 = d1[bit],
					i_D2 = d2[bit],
					i_D3 = d3[bit],
					i_D4 = d4[bit],
					i_D5 = d5[bit],
					i_D6 = d6[bit],
					o_Q = q[bit]
				)

		def get_ineg(z: Signal, invert: bool) -> Signal:
			if invert:
				a = Signal.like(z, name_suffix = '_n')
				m.d.comb += z.eq(~a)
				return a
			else:
				return z

		def get_oneg(a: Signal, invert: bool) -> Signal:
			if invert:
				z = Signal.like(a, name_suffix = '_n')
				m.d.comb += z.eq(~a)
				return z
			else:
				return a

		if 'i' in pin.dir:
			if pin.xdr < 2:
				pin_i  = get_ineg(pin.i,  i_invert)
			elif pin.xdr == 2:
				pin_i0 = get_ineg(pin.i0, i_invert)
				pin_i1 = get_ineg(pin.i1, i_invert)
			elif pin.xdr == 4:
				pin_i0 = get_ineg(pin.i0, i_invert)
				pin_i1 = get_ineg(pin.i1, i_invert)
				pin_i2 = get_ineg(pin.i2, i_invert)
				pin_i3 = get_ineg(pin.i3, i_invert)
			elif pin.xdr == 7:
				pin_i0 = get_ineg(pin.i0, i_invert)
				pin_i1 = get_ineg(pin.i1, i_invert)
				pin_i2 = get_ineg(pin.i2, i_invert)
				pin_i3 = get_ineg(pin.i3, i_invert)
				pin_i4 = get_ineg(pin.i4, i_invert)
				pin_i5 = get_ineg(pin.i5, i_invert)
				pin_i6 = get_ineg(pin.i6, i_invert)
		if 'o' in pin.dir:
			if pin.xdr < 2:
				pin_o  = get_oneg(pin.o,  o_invert)
			elif pin.xdr == 2:
				pin_o0 = get_oneg(pin.o0, o_invert)
				pin_o1 = get_oneg(pin.o1, o_invert)
			elif pin.xdr == 4:
				pin_o0 = get_oneg(pin.o0, o_invert)
				pin_o1 = get_oneg(pin.o1, o_invert)
				pin_o2 = get_oneg(pin.o2, o_invert)
				pin_o3 = get_oneg(pin.o3, o_invert)
			elif pin.xdr == 7:
				pin_o0 = get_oneg(pin.o0, o_invert)
				pin_o1 = get_oneg(pin.o1, o_invert)
				pin_o2 = get_oneg(pin.o2, o_invert)
				pin_o3 = get_oneg(pin.o3, o_invert)
				pin_o4 = get_oneg(pin.o4, o_invert)
				pin_o5 = get_oneg(pin.o5, o_invert)
				pin_o6 = get_oneg(pin.o6, o_invert)

		i = o = t = None
		if 'i' in pin.dir:
			i = Signal(pin.width, name = f'{pin.name}_xdr_i')
		if 'o' in pin.dir:
			o = Signal(pin.width, name = f'{pin.name}_xdr_o')
		if pin.dir in ('oe', 'io'):
			t = Signal(pin.width, name = f'{pin.name}_xdr_t')

		if pin.xdr == 0:
			if 'i' in pin.dir:
				i = pin_i
			if 'o' in pin.dir:
				o = pin_o
			if pin.dir in ('oe', 'io'):
				t = ~pin.oe.replicate(pin.width)
		elif pin.xdr == 1:
			if 'i' in pin.dir:
				get_ireg(pin.i_clk, i, pin_i)
			if 'o' in pin.dir:
				get_oreg(pin.o_clk, pin_o, o)
			if pin.dir in ('oe', 'io'):
				get_oereg(pin.o_clk, ~pin.oe, t)
		elif pin.xdr == 2:
			if 'i' in pin.dir:
				get_iddr(pin.i_clk, i, pin_i0, pin_i1)
			if 'o' in pin.dir:
				get_oddr(pin.o_clk, pin_o0, pin_o1, o)
			if pin.dir in ('oe', 'io'):
				get_oereg(pin.o_clk, ~pin.oe, t)
		elif pin.xdr == 4:
			if 'i' in pin.dir:
				get_iddrx2(pin.i_clk, pin.i_fclk, i, pin_i0, pin_i1, pin_i2, pin_i3)
			if 'o' in pin.dir:
				get_oddrx2(pin.o_clk, pin.o_fclk, pin_o0, pin_o1, pin_o2, pin_o3, o)
			if pin.dir in ('oe', 'io'):
				get_oereg(pin.o_clk, ~pin.oe, t)
		elif pin.xdr == 7:
			if 'i' in pin.dir:
				get_iddr71b(pin.i_clk, pin.i_fclk, i, pin_i0, pin_i1, pin_i2, pin_i3, pin_i4, pin_i5, pin_i6)
			if 'o' in pin.dir:
				get_oddr71b(pin.o_clk, pin.o_fclk, pin_o0, pin_o1, pin_o2, pin_o3, pin_o4, pin_o5, pin_o6, o)
			if pin.dir in ('oe', 'io'):
				get_oereg(pin.o_clk, ~pin.oe, t)
		else:
			raise ValueError(f'Invalid gearing {pin.xdr} for pin {pin.name}, must be one of, 0, 1, 2, 4, or 7')

		return (i, o, t)

	def get_input(self, pin: Pin, port: Record, attrs: Attrs, invert: bool) -> Module:
		self._check_feature(
			'single-ended input', pin, attrs, valid_xdrs = (0, 1, 2, 4, 7), valid_attrs = True
		)

		m = Module()
		i, o, t = self._get_xdr_buffer(m, pin, i_invert = invert)
		for bit in range(pin.width):
			m.submodules[f'{pin.name}_{bit}'] = Instance(
				'IB',
				i_I = port.io[bit],
				o_O = i[bit]
			)
		return m

	def get_output(self, pin: Pin, port: Record, attrs: Attrs, invert: bool) -> Module:
		self._check_feature(
			'single-ended output', pin, attrs, valid_xdrs = (0, 1, 2, 4, 7), valid_attrs = True
		)

		m = Module()
		i, o, t = self._get_xdr_buffer(m, pin, o_invert = invert)
		for bit in range(pin.width):
			m.submodules[f'{pin.name}_{bit}'] = Instance(
				'OB',
				i_I = o[bit],
				o_O = port.io[bit]
			)
		return m

	def get_tristate(self, pin: Pin, port: Record, attrs: Attrs, invert: bool) -> Module:
		self._check_feature(
			'single-ended tristate', pin, attrs, valid_xdrs = (0, 1, 2, 4, 7), valid_attrs = True
		)

		m = Module()
		i, o, t = self._get_xdr_buffer(m, pin, o_invert = invert)
		for bit in range(pin.width):
			m.submodules[f'{pin.name}_{bit}'] = Instance(
				'OBZ',
				i_T = t[bit],
				i_I = o[bit],
				o_O = port.io[bit]
			)
		return m

	def get_input_output(self, pin: Pin, port: Record, attrs: Attrs, invert: bool) -> Module:
		self._check_feature(
			'single-ended input/output', pin, attrs, valid_xdrs = (0, 1, 2, 4, 7), valid_attrs = True
		)

		m = Module()
		i, o, t = self._get_xdr_buffer(m, pin, i_invert = invert, o_invert = invert)
		for bit in range(pin.width):
			m.submodules[f'{pin.name}_{bit}'] = Instance(
				'BB',
				i_T = t[bit],
				i_I = o[bit],
				o_O = i[bit],
				io_B = port.io[bit]
			)
		return m

	def get_diff_input(self, pin: Pin, port: Record, attrs: Attrs, invert: bool) -> Module:
		self._check_feature(
			'differential input', pin, attrs, valid_xdrs = (0, 1, 2, 4, 7), valid_attrs = True
		)

		m = Module()
		i, o, t = self._get_xdr_buffer(m, pin, i_invert = invert)
		for bit in range(pin.width):
			m.submodules[f'{pin.name}_{bit}'] = Instance(
				'IB',
				i_I = port.p[bit],
				o_O = i[bit]
			)
		return m

	def get_diff_output(self, pin: Pin, port: Record, attrs: Attrs, invert: bool) -> Module:
		self._check_feature(
			'differential output', pin, attrs, valid_xdrs = (0, 1, 2, 4, 7), valid_attrs = True
		)

		m = Module()
		i, o, t = self._get_xdr_buffer(m, pin, o_invert = invert)
		for bit in range(pin.width):
			m.submodules[f'{pin.name}_{bit}'] = Instance(
				'OB',
				i_I = o[bit],
				o_O = port.p[bit],
			)
		return m

	def get_diff_tristate(self, pin: Pin, port: Record, attrs: Attrs, invert: bool) -> Module:
		self._check_feature(
			'differential tristate', pin, attrs, valid_xdrs = (0, 1, 2, 4, 7), valid_attrs = True
		)

		m = Module()
		i, o, t = self._get_xdr_buffer(m, pin, o_invert = invert)
		for bit in range(pin.width):
			m.submodules[f'{pin.name}_{bit}'] = Instance(
				'OBZ',
				i_T = t[bit],
				i_I = o[bit],
				o_O = port.p[bit],
			)
		return m

	def get_diff_input_output(self, pin: Pin, port: Record, attrs: Attrs, invert: bool) -> Module:
		self._check_feature(
			'differential input/output', pin, attrs, valid_xdrs = (0, 1, 2, 4, 7), valid_attrs = True
		)

		m = Module()
		i, o, t = self._get_xdr_buffer(m, pin, i_invert = invert, o_invert = invert)
		for bit in range(pin.width):
			m.submodules[f'{pin.name}_{bit}'] = Instance(
				'BB',
				i_T = t[bit],
				i_I = o[bit],
				o_O = i[bit],
				io_B = port.p[bit],
			)
		return m

	# CDC primitives are not currently specialized for ECP5.
	# While Diamond supports false path constraints; nextpnr-ecp5 does not.