;	6502-emulator kerete (kezzel irt resz; a generator a cpu6502.ras elejere masolja).
;	TVC-lapok (teljes 64K RAM, $B0 lapozas mellett):
CPU_JTL	EQU	$F8
CPU_PT	EQU	$FA
CPU_ZP	EQU	$FC
CPU_STK	EQU	$FD
CPU_IO	EQU	$FE
CPU_ZERO	EQU	$FF
;	$F800 ugrotabla also byte, $F900 felso byte, $FA00 laptabla (6502-lap -> TVC-lap), $FB00 erintett lapok,
;	$FC00 6502 nullas lap, $FD00 6502 verem, $FE00 I/O ($D000-$DFFF), $FF00 ures lap (0 = BRK)

		jp	CpuKodVege

;	------------------------------------------------ valtozok
	CpuS:
		db	$FF
	CpuVF:
		db	0
	CpuDF:
		db	0
	CpuIF:
		db	0
	CpuNDelta:
		db	0
	CpuTmp:
		dw	0
	CpuSVal:
		db	0
	CpuSLen:
		db	0
	CpuSPS:
		dw	0
	CpuSaveSP:
		dw	0
	CpuHivS:
		db	0
	CpuErr:
		db	0
	CpuErrOp:
		db	0
	CpuErrCim:
		dw	0
	CpuPool:
		db	0
	CpuPoolMin:
		db	0
	CpuPoolMax:
		db	CPU_JTL
	CpuImgLap:
		db	0
	CpuImg6502:
		db	0
	CpuImgDb:
		db	0
	CpuCim:
		dw	0
	CpuA:
		db	0
	CpuRtiP:
		db	0
	CpuRtiLo:
		db	0
	CpuRtiHi:
		db	0
	CpuLogN:
		db	0
	CpuLogP:
		dw	0
	CpuLog:
		ds	256
	CpuAux:
		ds	16
	CpuAuxTop:
		db	0

;	------------------------------------------------ CpuInit: tablak (hivas normal veremmel, $B0 lapozasban)
;	be: CpuImgLap = a .sid kepenek elso TVC-lapja, CpuImg6502 = elso 6502-lapja, CpuImgDb = lapok szama,
;	CpuPoolMin = az elso lap, amit a foglalas hasznalhat (felfele, a $F7-ig)
	CpuInit:
		ld	hl,CpuJtForras
		ld	de,$F800
		ld	b,0
	CiJt:
		ld	a,(hl)
		ld	(de),a
		inc	hl
		inc	d
		ld	a,(hl)
		ld	(de),a
		dec	d
		inc	hl
		inc	e
		djnz	CiJt
		;	laptabla: minden = ures; 0 = ZP, 1 = verem, $D0-$DF = I/O
		ld	hl,$FA00
	CiPt:
		ld	(hl),CPU_ZERO
		inc	l
		jr	nz,CiPt
		ld	(hl),CPU_ZP
		inc	l
		ld	(hl),CPU_STK
		ld	l,$D0
		ld	b,16
	CiIo:
		ld	(hl),CPU_IO
		inc	l
		djnz	CiIo
		;	a .sid kepe
		ld	a,(CpuImg6502)
		ld	l,a
		ld	a,(CpuImgDb)
		ld	b,a
		ld	a,(CpuImgLap)
	CiImg:
		ld	(hl),a
		inc	a
		inc	l
		djnz	CiImg
		;	erintett lapok, ZP, verem, I/O, ures lap: 0
		ld	hl,$FB00
		ld	de,$FB01
		ld	bc,$04FF
		ld	(hl),0
		ldir
		ld	a,$37
		ld	($FC01),a
		ld	a,$1B
		ld	($FE11),a
		ld	a,$FF
		ld	(CpuS),a
		ld	a,(CpuPoolMin)
		ld	(CpuPool),a
		xor	a
		ld	(CpuVF),a
		ld	(CpuDF),a
		ld	(CpuIF),a
		ld	(CpuErr),a
		ld	hl,0
		push	hl
		pop	af
		ex	af,af'
		ret

;	------------------------------------------------ CpuHiv: 6502-rutin hivasa (CpuCim, A = CpuA), di kell!
	CpuHiv:
		ld	(CpuSaveSP),sp
		ld	a,(CpuS)
		ld	(CpuHivS),a
		ld	l,a
		ld	h,CPU_STK
		ld	(hl),$FF
		dec	l
		ld	(hl),$EF
		dec	l
		ld	a,l
		ld	(CpuS),a
		ex	af,af'
		ld	a,(CpuA)
		ex	af,af'
		ld	bc,0
		ld	de,(CpuCim)
		ld	l,d
		jp	CpuRtiJmp

;	BRK ($00): a visszateres a $FFF0-ra (vagy hiba)
	CpuStop:
		ld	sp,(CpuSaveSP)
		ld	a,(CpuS)
		ld	hl,CpuHivS
		cp	(hl)
		ret	z
		ld	a,1
		ld	(CpuErr),a
		ret

	CpuIllegal:
		ld	hl,-2
		add	hl,sp
		ld	(CpuErrCim),hl
		ld	a,(hl)
		ld	(CpuErrOp),a
		ld	a,2
		ld	(CpuErr),a
		ld	sp,(CpuSaveSP)
		ret

;	------------------------------------------------ D jelzo: A = 0/1 -> ADC/SBC kezelok cserelese
	CpuSetD:
		ld	(CpuDF),a
		ld	ix,CpuBcdLista
	CsdKor:
		ld	a,(ix+0)
		or	a
		jr	z,CsdVeg
		ld	l,a
		ld	h,CPU_JTL
		ld	a,(CpuDF)
		or	a
		jr	nz,CsdBcd
		ld	a,(ix+1)
		ld	(hl),a
		inc	h
		ld	a,(ix+2)
		ld	(hl),a
		jr	CsdTov
	CsdBcd:
		ld	a,(ix+3)
		ld	(hl),a
		inc	h
		ld	a,(ix+4)
		ld	(hl),a
	CsdTov:
		ld	de,5
		add	ix,de
		jr	CsdKor
	CsdVeg:
		pop	hl
		ld	e,h
		ld	h,CPU_JTL
		ld	a,(hl)
		inc	h
		ld	h,(hl)
		ld	l,a
		jp	(hl)

;	------------------------------------------------ PHP
	CpuPhp:
		ex	af,af'
		ld	(CpuSPS),sp
		ld	sp,CpuAuxTop
		push	af
		ld	sp,(CpuSPS)
		ex	af,af'
		ld	a,(CpuAuxTop-2)
		ld	d,a
		and	$81
		ld	e,a
		bit	6,d
		jr	z,CphZ
		set	1,e
	CphZ:
		ld	a,(CpuVF)
		or	a
		jr	z,CphV
		set	6,e
	CphV:
		ld	a,(CpuDF)
		or	a
		jr	z,CphD
		set	3,e
	CphD:
		ld	a,(CpuIF)
		or	a
		jr	z,CphI
		set	2,e
	CphI:
		ld	a,e
		or	$30
		ld	e,a
		ld	a,(CpuS)
		ld	l,a
		ld	h,CPU_STK
		ld	(hl),e
		dec	l
		ld	a,l
		ld	(CpuS),a
		pop	hl
		ld	e,h
		ld	h,CPU_JTL
		ld	a,(hl)
		inc	h
		ld	h,(hl)
		ld	l,a
		jp	(hl)

;	------------------------------------------------ jelzok beallitasa a P byte-bol (A = P), D = P marad
	CpuPAllit:
		ld	d,a
		and	$40
		ld	(CpuVF),a
		ld	a,d
		and	4
		ld	(CpuIF),a
		ld	a,d
		and	$81
		ld	e,a
		bit	1,d
		jr	z,CpaZ
		set	6,e
	CpaZ:
		ex	af,af'
		ld	h,a
		ld	l,e
		ld	(CpuSPS),sp
		ld	sp,CpuAuxTop
		push	hl
		pop	af
		ld	sp,(CpuSPS)
		ex	af,af'
		jp	(ix)

	CpuPlp:
		ld	ix,CplTov
		jp	CpuPAllit
	CplTov:
		ld	a,d
		rrca
		rrca
		rrca
		and	1
		jp	CpuSetD

	CpuRti:
		ld	a,(CpuRtiP)
		ld	ix,CrtTov
		jp	CpuPAllit
	CrtTov:
		ld	a,(CpuRtiLo)
		ld	e,a
		ld	a,(CpuRtiHi)
		ld	l,a
		jp	CpuRtiJmp

;	------------------------------------------------ lassu iras: D = CPU_IO / CPU_ZERO, L = 6502 felso, E = also
	CpuSlowSt:
		ld	a,d
		cp	CPU_ZERO
		jr	z,CpuFoglal
		ld	d,l
		ld	l,e
		ld	h,CPU_IO
		ld	a,(CpuSVal)
		ld	(hl),a
		ld	a,d
		and	$FC
		cp	$D4
		jr	nz,CssKesz
		ld	a,e
		and	$1F
		cp	25
		jr	nc,CssKesz
		ld	e,a
		ld	a,(CpuLogN)
		cp	128
		jr	nc,CssKesz
		inc	a
		ld	(CpuLogN),a
		ld	hl,(CpuLogP)
		ld	(hl),e
		inc	hl
		ld	a,(CpuSVal)
		ld	(hl),a
		inc	hl
		ld	(CpuLogP),hl
	CssKesz:
		pop	hl
		ld	e,h
		ld	h,CPU_JTL
		ld	a,(hl)
		inc	h
		ld	h,(hl)
		ld	l,a
		jp	(hl)

	CpuSlowRmw:
		ld	a,d
		cp	CPU_ZERO
		jr	nz,CssKesz
	;	uj lap a 6502-lapnak (L), az utasitas ujra
	CpuFoglal:
		ld	a,(CpuPoolMax)
		ld	d,a
		ld	a,(CpuPool)			;	felfele foglal (a sorban irt lapok egymas utan kerulnek -> a kod atfolyhat)
		cp	d
		jr	nc,CpuNincsHely
		ld	h,CPU_PT
		ld	(hl),a
		inc	a
		ld	(CpuPool),a
		dec	a
		ld	h,a
		ld	l,0
		xor	a
	CfTorl:
		ld	(hl),a
		inc	l
		jr	nz,CfTorl
		ld	hl,0
		add	hl,sp
		ld	a,(CpuSLen)
		ld	e,a
		ld	d,0
		or	a
		sbc	hl,de
		ld	sp,hl
		jr	CssKesz
	CpuNincsHely:
		ld	a,3
		ld	(CpuErr),a
		ld	sp,(CpuSaveSP)
		ret
