
import RPIO
import time

def pin_init():
	pass

def pin_set(pin,mode=0):
	RPIO.setup(pin, RPIO.IN if mode else RPIO.OUT)

def pin_write(pin,x):
	RPIO.output(pin, x)

def pin_read(pin):
	return RPIO.input(pin)

def pin_clean():
	RPIO.cleanup()

class spi_class(object):
	"""docstring for spi_class"""
	def __init__(self,mo,mi,clk):
		self.mo = mo
		self.mi = mi
		self.clk = clk
		pin_set(self.mo  ,0)
		pin_set(self.mi  ,1)
		pin_set(self.clk ,0)

	def _in(self):
		return pin_read(self.mi)
	def _out(self,x):
		pin_write(self.mo,x)
	def _clk(self,x):
		pin_write(self.clk,x)
	def _enable(self,cs):
		pin_write(cs,0)
	def _disable(self,cs):
		pin_write(cs,1)

	def transfer(self,cs,dat):
		rbuf = []
		self._enable(cs)
		for byte in dat:
			rbuf.append(0)
			self._clk(0)
			for i in [7,6,5,4,3,2,1,0]:
				self._out(1 if byte & (0x1<<i) else 0)
				self._clk(1)
				if self._in():
					rbuf[-1] |= 0x1<<i
				self._clk(0)
		self._disable(cs)
		# print '# %s (%s)' %(dat,rbuf)
		return rbuf

class base_class(object):
	"""docstring for base_class"""
	localAddress  = [1,2,3,4,5]
	channel       = [111]
	configuration = [
			# (addr,[value...])
			(0x00,[0xfb]),
			(0x11,[32]),
			(0x12,[32])
		]
	def __init__(self, spi, ce_pin, irq_pin, cs_pin, **kargs):
		self.spi     = spi
		self.ce_pin  = ce_pin
		self.irq_pin = irq_pin
		self.cs_pin  = cs_pin
		pin_set(self.ce_pin  ,0)
		pin_set(self.irq_pin ,1)
		pin_set(self.cs_pin  ,0)
		# re-config arg
		re_config = [
				# (name,addr)
				('localAddress',0x0b),
				('channel',0x05)
			]
		# Ext config
		for name,_ in re_config:
			if kargs.has_key(name):
				setattr(self,name,kargs[name])
		# re config
		for name,addr in re_config:
			self.configuration.append((addr,getattr(self,name)))
		# load config
		self.configurate()
		# 
		self._disable_chip()

	def _enable_chip(self):
		pin_write(self.ce_pin,1)
	def _disable_chip(self):
		pin_write(self.ce_pin,0)

	def _transfer(self,x):
		rec = self.spi.transfer(self.cs_pin,x)
		# print 'TRANS\t%s\t%s' %(map(hex,x),map(hex,rec))
		return rec

	def _get_status(self):
		return self._transfer([0xff])[0]

	def _get_reg(self,addr):
		rec = self._transfer([0x1f&addr]+[0])
		return rec[-1]

	def _set_reg(self,addr,byte,mask=0xff):
		if mask==0xff:
			self._set_reg_bytes(addr,[byte])
		else:
			last = self._get_reg(addr)
			new  = last&(~mask)
			new |= byte&mask
			self._set_reg_bytes(addr,[new])

	def _set_reg_bytes(self,addr,_bytes):
		self._transfer([0x20+(0x1f&addr)]+_bytes)

	def _get_rx_payload(self):
		rec = self._transfer([0x61]+[0]*32)
		return rec[1:]

	def _set_tx_payload(self,x):
		txbuf = [0]*32
		for i,item in enumerate(x):
			if i>=32:
				break
			txbuf[i] = item
		self._transfer([0xa0]+txbuf)

	def _set_tx_addr(self,addr):
		addr5 = [0]*5
		for i,item in enumerate(addr):
			if i>=5:
				break
			addr5[i] = item
		self._set_reg_bytes(0x10,addr5)

	def _set_rx_addr(self,addr,p=1):
		addr5 = [0]*5
		for i,item in enumerate(addr):
			if i>=5:
				break
			addr5[i] = item
		self._set_reg_bytes(0x0a+p,addr5)

	def rxMode(self):
		self._set_reg(0,0x01,0x01)
		self._set_rx_addr(self.localAddress)
		# Active RX mode is started by setting CE high
		self._enable_chip()
		time.sleep(0.001)

	def txMode(self):
		self._set_reg(0,0x00,0x01)

	def write(self,addr,dat):
		# clear TX_DS
		self._set_reg(0x07,1<<5,1<<5)
		self._set_reg(0x07,1<<6,1<<6)
		# 
		self._set_tx_addr(addr)
		self._set_rx_addr(addr,p=0)
		self._set_tx_payload(dat)
		# A high pulse on CE starts the transmission
		self._enable_chip()
		self._disable_chip()

	def read(self):
		dat = self._get_rx_payload()
		# clear RX_DR
		self._set_reg(0x07,1<<6,1<<6)
		return dat

	def available(self):
		sta = self._get_status()
		return True if sta&(1<<6) and sta&(111<<1)==(1<<1) else False

	def write_done(self):
		sta = self._get_status()
		return True if sta&(1<<5) else False

	def configurate(self):
		for addr,value in self.configuration:
			print "CONFIG\t%s\t%s" %(hex(addr),map(hex,value))
			self._set_reg_bytes(addr,value)

	def dump_reg(self):
		print '-------dump--------'
		for i in range(0x17+1):
			print '%s\t%s' %(hex(i),hex(self._get_reg(i)))
		print '-------------------'

if __name__ == '__main__':
	print '== Testing =='
	print 'localAddress = [1,1,1,1,1]'
	print 'remoteAddress = [2,2,2,2,2]'
	pin_init()
	chip = base_class(
			spi     = spi_class(mo=18,mi=23,clk=22),
			ce_pin  = 17,
			irq_pin = 4,
			cs_pin  = 27,
			# ext
			localAddress =[1,1,1,1,1],
			# channel      =10
		)
	chip.dump_reg()
	chip.txMode()
	chip.write([2,2,2,2,2],[1,2,3])
	chip.dump_reg()
	time.sleep(1)
