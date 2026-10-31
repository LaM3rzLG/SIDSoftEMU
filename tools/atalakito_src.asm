;	TVC-s atalakito: SID-irasok -> .STC (a tools/tvc_atalakito.py PONTOS masa; ellenorzes: tools/z80_at_teszt.py)
;	Hivasok (normal veremmel, $B0 lapozasban; IX, IY szabadon):
;	  AtInit      - kimenet ($5000-tol), hangok, hash-tablak ($EF00-$F4FF), sorok ($F500-$F7FF)
;	  AtKepkocka  - egy kepkocka: a CpuLog (CpuLogN par) feldolgozasa, 3 hang: burkolo, allapot, kodolas.
;	                AtStop = 1, ha mar nincs hely (a kepkocka nem kerult be)
;	  AtVege      - a sorok kiuritese, VEGE ($11 -> elso rekord), fejlec. Hossz: AtHossz
;	Hang-struktura (IX, {VMERET} byte):
;	  F, PW, vezerlo, A D S R, szint (8.8), allapot, gate | wp, wend (lap), start | S (4) | elso | sor: fej, db, lap |
;	  hash-lap | cel (4) | setalas: aktiv, a, p, SS (4), u, fr, best u, best fr, best SS (4)

		jp	AtKodVege

	AtHangok:
		ds	{VMERET3}
	AtNext:
		db	0
	AtStop:
		db	0
	AtTele:
		db	0
	AtVol:
		db	0
	AtFinal:
		db	0
	AtFull:
		db	0
	AtCel:
		db	0
	AtCost:
		db	0
	AtBuf:
		ds	8
	AtLS:
		ds	4
	AtHossz:
		dw	0
	AtKepek:
		dw	0
	AtNRef:
		dw	0
	AtAtt:
{ATT}
	AtSzint:
{SZINT}

;	------------------------------------------------ AtInit
	AtInit:
		ld	hl,AtHangok
		ld	b,{VMERET3}
		xor	a
	AiT:
		ld	(hl),a
		inc	hl
		djnz	AiT
		ld	hl,$EF00
		ld	de,$EF01
		ld	bc,$05FF
		ld	(hl),0
		ldir
		ld	a,$50
		ld	(AtNext),a
		xor	a
		ld	(AtStop),a
		ld	(AtTele),a
		ld	(AtVol),a
		ld	hl,0
		ld	(AtKepek),hl
		ld	(AtNRef),hl
		ld	ix,AtHangok
		ld	c,0
	AiH:
		ld	(ix+{SPW}),128
		ld	(ix+{TPW}),128
		ld	(ix+{ELSO}),1
		ld	(ix+{STATE}),2
		ld	a,$F5
		add	a,c
		ld	(ix+{QPG}),a
		ld	a,c
		add	a,a
		add	a,$EF
		ld	(ix+{HPG}),a
		call	AtBlokk
		ld	(ix+{WPHI}),a
		ld	(ix+{STHI}),a
		inc	a
		ld	(ix+{WEND}),a
		ld	a,c
		or	a
		ld	a,0
		jp	nz,AiNem0
		ld	a,6
	AiNem0:
		ld	(ix+{WPLO}),a
		ld	(ix+{STLO}),a
		ld	de,{VMERET}
		add	ix,de
		inc	c
		ld	a,c
		cp	3
		jp	nz,AiH
		ret

;	uj 256 byte-os blokk: A = lapja; carry = nincs hely
	AtBlokk:
		ld	a,(AtNext)
		cp	$EF
		jp	nc,AbTele
		inc	a
		ld	(AtNext),a
		dec	a
		or	a
		ret
	AbTele:
		ld	a,1
		ld	(AtTele),a
		scf
		ret

;	------------------------------------------------ AtKepkocka
	AtKepkocka:
		ld	a,(AtNext)
		cp	$E4					;	3 KB tartalek (mint a Python: SONG_END - next < 3072)
		jp	c,AkVan
		ld	a,1
		ld	(AtStop),a
		ret
	AkVan:
		ld	a,(CpuLogN)
		or	a
		jp	z,AkHangok
		ld	b,a
		ld	hl,CpuLog
	AkLog:
		ld	a,(hl)
		inc	hl
		ld	c,(hl)
		inc	hl
		push	bc
		push	hl
		cp	21
		jp	nc,AkNem
		ld	ix,AtHangok
		ld	de,{VMERET}
	AkDiv:
		cp	7
		jp	c,AkDivK
		sub	7
		add	ix,de
		jp	AkDiv
	AkDivK:
		call	AtIras
		jp	AkTov
	AkNem:
		cp	24
		jp	nz,AkTov
		ld	a,c
		and	15
		ld	(AtVol),a
	AkTov:
		pop	hl
		pop	bc
		djnz	AkLog
	AkHangok:
		ld	ix,AtHangok
		ld	b,3
	AkH:
		push	bc
		call	AtFel
		call	AtAllapot
		call	AtFel
		call	AtQPush
		xor	a
		ld	(AtFinal),a
		call	AtDont
		ld	de,{VMERET}
		add	ix,de
		pop	bc
		djnz	AkH
		ld	hl,(AtKepek)
		inc	hl
		ld	(AtKepek),hl
		ret

;	------------------------------------------------ regiszter-iras: A = k (0..6), C = ertek
	AtIras:
		or	a
		jp	nz,Ir1
		ld	(ix+{FLO}),c
		ret
	Ir1:
		dec	a
		jp	nz,Ir2
		ld	(ix+{FHI}),c
		ret
	Ir2:
		dec	a
		jp	nz,Ir3
		ld	(ix+{PWLO}),c
		ret
	Ir3:
		dec	a
		jp	nz,Ir4
		ld	a,c
		and	15
		ld	(ix+{PWHI}),a
		ret
	Ir4:
		dec	a
		jp	nz,Ir5
		ld	a,c
		and	1
		ld	b,a
		jp	z,Ir4Nul
		ld	a,(ix+{GATE})
		or	a
		jp	nz,Ir4Kesz
		ld	(ix+{STATE}),0
		jp	Ir4Kesz
	Ir4Nul:
		ld	a,(ix+{GATE})
		or	a
		jp	z,Ir4Kesz
		ld	(ix+{STATE}),2
	Ir4Kesz:
		ld	(ix+{GATE}),b
		ld	(ix+{CTRL}),c
		ret
	Ir5:
		dec	a
		jp	nz,Ir6
		ld	a,c
		rrca
		rrca
		rrca
		rrca
		and	15
		ld	(ix+{RA}),a
		ld	a,c
		and	15
		ld	(ix+{RD}),a
		ret
	Ir6:
		ld	a,c
		rrca
		rrca
		rrca
		rrca
		and	15
		ld	(ix+{RS}),a
		ld	a,c
		and	15
		ld	(ix+{RR}),a
		ret

;	------------------------------------------------ burkolo: fel kepkocka
	AtFel:
		ld	l,(ix+{LVLLO})
		ld	h,(ix+{LVLHI})
		ld	a,(ix+{STATE})
		or	a
		jp	nz,Fe1
		ld	a,(ix+{RA})
		call	AtAttDE
		add	hl,de
		jp	c,FeMax
		ld	a,h
		cp	$FF
		jp	c,FeTar
	FeMax:
		ld	hl,$FF00
		ld	(ix+{STATE}),1
		jp	FeTar
	Fe1:
		dec	a
		jp	nz,Fe2
		ld	a,(ix+{RS})
		ld	e,a
		add	a,a
		add	a,a
		add	a,a
		add	a,a
		add	a,e
		ld	(AtCel),a
		cp	h
		jp	c,FeDec
		jp	nz,FeTar
		ld	a,l
		or	a
		jp	z,FeTar
	FeDec:
		ld	a,(ix+{RD})
		call	AtAttDE
		call	AtShift
		or	a
		sbc	hl,de
		jp	c,FeCel
		ld	a,(AtCel)
		cp	h
		jp	z,FeTar
		jp	c,FeTar
	FeCel:
		ld	a,(AtCel)
		ld	h,a
		ld	l,0
		jp	FeTar
	Fe2:
		ld	a,(ix+{RR})
		call	AtAttDE
		call	AtShift
		or	a
		sbc	hl,de
		jp	nc,FeTar
		ld	hl,0
	FeTar:
		ld	(ix+{LVLLO}),l
		ld	(ix+{LVLHI}),h
		ret

;	DE = AtAtt[A]
	AtAttDE:
		push	hl
		add	a,a
		ld	e,a
		ld	d,0
		ld	hl,AtAtt
		add	hl,de
		ld	e,(hl)
		inc	hl
		ld	d,(hl)
		pop	hl
		ret

;	DE >>= eltolas(H): H >= 93: 0, >= 54: 1, >= 26: 2, >= 14: 3, >= 6: 4, kulonben 5
	AtShift:
		ld	a,h
		ld	b,0
		cp	93
		jp	nc,ShD
		inc	b
		cp	54
		jp	nc,ShD
		inc	b
		cp	26
		jp	nc,ShD
		inc	b
		cp	14
		jp	nc,ShD
		inc	b
		cp	6
		jp	nc,ShD
		inc	b
	ShD:
		ld	a,b
		or	a
		ret	z
	ShK:
		srl	d
		rr	e
		djnz	ShK
		ret

;	------------------------------------------------ TVC-allapot (cel) a hang regisztereibol
	AtAllapot:
		ld	a,(AtVol)
		ld	b,a
		ld	e,(ix+{LVLHI})
		ld	d,0
		ld	hl,0
		or	a
		jp	z,AlMul0
	AlMul:
		add	hl,de
		djnz	AlMul
	AlMul0:
		srl	h
		rr	l
		srl	h
		rr	l
		srl	h
		rr	l
		srl	h
		rr	l
		ld	de,AtSzint
		add	hl,de
		ld	c,(hl)				;	C = szint 0..5
		ld	a,(ix+{CTRL})
		and	8
		jp	nz,AlCsend
		ld	a,(ix+{CTRL})
		and	$F0
		jp	z,AlCsend
		ld	a,c
		or	a
		jp	nz,AlVan
	AlCsend:
		ld	(ix+{TSL}),0
		ret
	AlVan:
		ld	l,(ix+{FLO})
		ld	h,(ix+{FHI})
		ld	d,h
		ld	e,l
		srl	d
		rr	e
		srl	d
		rr	e
		or	a
		sbc	hl,de
		srl	d
		rr	e
		srl	d
		rr	e
		srl	d
		rr	e
		srl	d
		rr	e
		add	hl,de
		srl	d
		rr	e
		srl	d
		rr	e
		srl	d
		rr	e
		add	hl,de				;	HL = F - F/4 + F/64 + F/512
		ld	a,(ix+{CTRL})
		bit	7,a
		jp	z,AlNemZaj
		srl	h
		rr	l
		srl	h
		rr	l
		srl	h
		rr	l
		srl	h
		rr	l
		ld	a,h
		or	l
		jp	nz,AlZ1
		inc	l
	AlZ1:
		ld	a,c
		add	a,10
		ld	(ix+{TSL}),a
		jp	AlSt
	AlNemZaj:
		bit	6,a
		jp	z,AlNemNegy
		ld	a,c
		or	$80
		ld	(ix+{TSL}),a
		ld	a,(ix+{PWHI})
		rlca
		rlca
		rlca
		rlca
		and	$F0
		ld	b,a
		ld	a,(ix+{PWLO})
		rrca
		rrca
		rrca
		rrca
		and	15
		or	b
		ld	(ix+{TPW}),a
		jp	AlSt
	AlNemNegy:
		bit	5,a
		jp	z,AlHarom
		ld	(ix+{TSL}),c
		jp	AlSt
	AlHarom:
		ld	a,c
		add	a,5
		ld	(ix+{TSL}),a
	AlSt:
		ld	(ix+{TST0}),l
		ld	(ix+{TST1}),h
		ret

;	------------------------------------------------ sor: a cel a vegere
	AtQPush:
		ld	a,(ix+{QN})
		add	a,a
		add	a,a
		add	a,(ix+{QH})
		ld	l,a
		ld	h,(ix+{QPG})
		ld	a,(ix+{TST0})
		ld	(hl),a
		inc	l
		ld	a,(ix+{TST1})
		ld	(hl),a
		inc	l
		ld	a,(ix+{TSL})
		ld	(hl),a
		inc	l
		ld	a,(ix+{TPW})
		ld	(hl),a
		inc	(ix+{QN})
		ret

;	HL = &Q[A]
	AtQi:
		add	a,a
		add	a,a
		add	a,(ix+{QH})
		ld	l,a
		ld	h,(ix+{QPG})
		ret

;	A db elem eldobasa a sor elejerol (a setalas is ervenytelen)
	AtPop:
		ld	b,a
		add	a,a
		add	a,a
		add	a,(ix+{QH})
		ld	(ix+{QH}),a
		ld	a,(ix+{QN})
		sub	b
		ld	(ix+{QN}),a
		ld	(ix+{WACT}),0
		ret

;	Z = (HL) 4 byte == (DE) 4 byte; HL, DE nem valtozik (a sorban az L korbefordul)
	AtEq4:
		push	hl
		push	de
		ld	b,4
	Eq4:
		ld	a,(de)
		cp	(hl)
		jp	nz,Eq4Ki
		inc	de
		inc	hl
		djnz	Eq4
	Eq4Ki:
		pop	de
		pop	hl
		ret

;	DE = IX + A (a struktura egy mezoje)
	AtMezo:
		push	ix
		pop	de
		add	a,e
		ld	e,a
		ret	nc
		inc	d
		ret

;	A = hash(HL-n levo allapot): st0 ^ st1 ^ (sl << 1) ^ pw
	AtHash:
		push	hl
		ld	a,(hl)
		inc	hl
		xor	(hl)
		inc	hl
		ld	b,a
		ld	a,(hl)
		add	a,a
		xor	b
		inc	hl
		xor	(hl)
		pop	hl
		ret

;	H-tabla: H[A] = DE
	AtHIr:
		ld	l,a
		ld	h,(ix+{HPG})
		ld	(hl),e
		inc	h
		ld	(hl),d
		ret

;	------------------------------------------------ iras a kimenetbe: AtBuf, B byte -> DE = a rekord cime
	AtIr:
		ld	l,(ix+{WPLO})
		ld	h,(ix+{WPHI})
		ld	d,(ix+{WEND})
		ld	e,0
		ex	de,hl
		or	a
		sbc	hl,de				;	szabad = wend*256 - wp
		ld	a,b
		add	a,3
		ld	e,a
		ld	d,0
		or	a
		sbc	hl,de
		jp	nc,AirVan
		push	bc
		call	AtBlokk
		pop	bc
		ret	c					;	nincs hely (a Python itt hibat dob)
		ld	l,(ix+{WPLO})
		ld	h,(ix+{WPHI})
		ld	(hl),$11
		inc	hl
		ld	(hl),0
		inc	hl
		ld	(hl),a
		ld	(ix+{WPLO}),0
		ld	(ix+{WPHI}),a
		inc	a
		ld	(ix+{WEND}),a
	AirVan:
		ld	e,(ix+{WPLO})
		ld	d,(ix+{WPHI})
		push	de
		ld	hl,AtBuf
		ld	c,b
		ld	b,0
		ldir
		ld	(ix+{WPLO}),e
		ld	(ix+{WPHI}),d
		pop	de
		ret

;	------------------------------------------------ rekord: lit_bytes(S, Q[0], AtFull) -> AtBuf, B = hossz
	AtLitQ0:
		xor	a
		call	AtQi				;	HL = Q[0]
		push	hl
		ld	a,{SST0}
		call	AtMezo				;	DE = S
		call	AtLitEpit
		call	AtIr				;	DE = cim
		pop	hl
		call	AtHash
		call	AtHIr
		;	S = Q[0]
		xor	a
		call	AtQi
		ld	a,(hl)
		ld	(ix+{SST0}),a
		inc	l
		ld	a,(hl)
		ld	(ix+{SST1}),a
		inc	l
		ld	a,(hl)
		ld	(ix+{SSL}),a
		inc	l
		ld	a,(hl)
		ld	(ix+{SPW}),a
		ld	a,1
		jp	AtPop

;	HL = cel (sorban), DE = S -> AtBuf, B = hossz (AtFull = teljes)
	AtLitEpit:
		ld	iy,AtBuf+1
		ld	c,0
		ld	a,(AtFull)
		or	a
		jp	nz,LeSt2
		ld	a,(de)
		cp	(hl)
		jp	nz,LeStV
		inc	l
		ld	b,(hl)
		dec	l
		inc	de
		ld	a,(de)
		dec	de
		cp	b
		jp	z,LeSl
	LeStV:
		;	kulonbseg = T - S (16 bit)
		push	hl
		ld	a,(hl)
		inc	l
		ld	h,(hl)
		ld	l,a
		ld	a,(de)
		ld	b,a
		inc	de
		ld	a,(de)
		dec	de
		push	de
		ld	d,a
		ld	e,b
		or	a
		sbc	hl,de				;	HL = T - S
		pop	de
		ld	a,h
		or	a
		jp	nz,LeNeg
		bit	7,l
		jp	nz,LeSt2P
		jp	LeDelta
	LeNeg:
		inc	a
		jp	nz,LeSt2P
		bit	7,l
		jp	z,LeSt2P
	LeDelta:
		ld	(iy+0),l
		inc	iy
		pop	hl
		ld	c,2
		jp	LeSl
	LeSt2P:
		pop	hl
	LeSt2:
		set	0,c
		ld	a,(hl)
		ld	(iy+0),a
		inc	l
		ld	a,(hl)
		ld	(iy+1),a
		dec	l
		inc	iy
		inc	iy
	LeSl:
		inc	l
		inc	l
		inc	de
		inc	de
		ld	a,(AtFull)
		or	a
		jp	nz,LeSl2
		ld	a,(de)
		cp	(hl)
		jp	z,LePw
	LeSl2:
		set	2,c
		ld	a,(hl)
		ld	(iy+0),a
		inc	iy
	LePw:
		inc	l
		inc	de
		ld	a,(AtFull)
		or	a
		jp	nz,LePw2
		ld	a,(de)
		cp	(hl)
		jp	z,LeKesz
	LePw2:
		set	3,c
		ld	a,(hl)
		ld	(iy+0),a
		inc	iy
	LeKesz:
		ld	a,c
		ld	(AtBuf),a
		push	iy
		pop	hl
		ld	de,AtBuf
		or	a
		sbc	hl,de
		ld	b,l
		ret

;	------------------------------------------------ a dontes (Kodolo.dont)
	AtDont:
		ld	a,(ix+{QN})
		or	a
		ret	z
		ld	a,(ix+{ELSO})
		or	a
		jp	z,DoNem1
		ld	a,1
		ld	(AtFull),a
		call	AtLitQ0
		xor	a
		ld	(AtFull),a
		ld	(ix+{ELSO}),0
		jp	AtDont
	DoNem1:
		xor	a
		call	AtQi
		call	AtHash
		ld	l,a
		ld	h,(ix+{HPG})
		ld	e,(hl)
		inc	h
		ld	d,(hl)
		ld	a,d
		or	e
		jp	z,DoNoRef
		call	AtWalk
		or	a
		ret	nz					;	tobb kepkocka kell
		ld	a,(ix+{BU})
		or	a
		jp	z,DoNoRef
		call	AtLitCost
		cp	6
		jp	c,DoNoRef
		ld	a,$10
		ld	(AtBuf),a
		ld	a,(ix+{WA0})
		ld	(AtBuf+1),a
		ld	a,(ix+{WA1})
		ld	(AtBuf+2),a
		ld	a,(ix+{BU})
		ld	(AtBuf+3),a
		ld	b,4
		call	AtIr
		ld	a,(ix+{BS0})
		ld	(ix+{SST0}),a
		ld	a,(ix+{BS1})
		ld	(ix+{SST1}),a
		ld	a,(ix+{BSL})
		ld	(ix+{SSL}),a
		ld	a,(ix+{BPW})
		ld	(ix+{SPW}),a
		ld	hl,(AtNRef)
		inc	hl
		ld	(AtNRef),hl
		ld	a,(ix+{BFR})
		call	AtPop
		jp	AtDont
	DoNoRef:
		ld	a,{SST0}
		call	AtMezo				;	DE = S
		xor	a
		call	AtQi
		call	AtEq4
		jp	nz,DoLit
		;	S-sel egyezo sorozat hossza
		ld	c,1
	DoRun:
		ld	a,c
		cp	(ix+{QN})
		jp	nc,DoRunK
		call	AtQi
		ld	a,{SST0}
		call	AtMezo
		call	AtEq4
		jp	nz,DoRunK
		inc	c
		jp	DoRun
	DoRunK:
		ld	a,c
		cp	(ix+{QN})
		jp	nz,DoRunIr
		ld	a,(AtFinal)
		or	a
		jp	nz,DoRunIr
		ld	a,(ix+{QN})
		cp	{QMAX}
		ret	c					;	a sorozat meg folytatodhat
	DoRunIr:
		ld	a,c
		ld	b,1
		cp	1
		ld	a,0
		jp	z,DoRun1
		ld	a,c
		or	$80
	DoRun1:
		ld	(AtBuf),a
		push	bc
		call	AtIr
		ld	a,{SST0}
		push	de
		call	AtMezo
		ex	de,hl
		pop	de
		call	AtHash
		call	AtHIr
		pop	bc
		ld	a,c
		call	AtPop
		jp	AtDont
	DoLit:
		call	AtLitQ0
		jp	AtDont

;	------------------------------------------------ rekordok koltsege (litkoltseg) a Q[0..BFR)-re, S-tol; A = min(6, koltseg)
	AtLitCost:
		ld	a,{SST0}
		call	AtMezo
		ex	de,hl
		ld	de,AtLS
		ld	bc,4
		ldir
		xor	a
		ld	(AtCost),a
		ld	c,0					;	i
	LcKor:
		ld	a,c
		cp	(ix+{BFR})
		jp	nc,LcVeg
		call	AtQi
		ld	de,AtLS
		push	bc
		call	AtEq4
		pop	bc
		jp	nz,LcLit
		ld	hl,AtCost			;	egyezo sorozat: +1
		inc	(hl)
	LcRun:
		inc	c
		ld	a,c
		cp	(ix+{BFR})
		jp	nc,LcVizsg
		call	AtQi
		ld	de,AtLS
		push	bc
		call	AtEq4
		pop	bc
		jp	z,LcRun
		jp	LcVizsg
	LcLit:
		push	bc
		push	hl
		xor	a
		ld	(AtFull),a
		call	AtLitEpit			;	B = hossz
		ld	a,(AtCost)
		add	a,b
		ld	(AtCost),a
		pop	hl					;	LS = Q[i]
		ld	de,AtLS
		ld	bc,4
		ldir
		pop	bc
		inc	c
	LcVizsg:
		ld	a,(AtCost)
		cp	6
		jp	c,LcKor
		ld	a,6
		ret
	LcVeg:
		ld	a,(AtCost)
		ret

;	------------------------------------------------ setalas (Kodolo.setal), DE = a jelolt cime. A = 0 kesz, 1 = tobb kell
	AtWalk:
		ld	a,(ix+{WACT})
		or	a
		jp	z,WkUj
		ld	a,(ix+{WA0})
		cp	e
		jp	nz,WkUj
		ld	a,(ix+{WA1})
		cp	d
		jp	nz,WkUj
		ld	a,(ix+{WACT})
		cp	2
		jp	nz,WkKor
		xor	a					;	mar kesz volt
		ret
	WkUj:
		ld	(ix+{WACT}),1
		ld	(ix+{WA0}),e
		ld	(ix+{WA1}),d
		ld	(ix+{WP0}),e
		ld	(ix+{WP1}),d
		ld	a,(ix+{SST0})
		ld	(ix+{WS0}),a
		ld	(ix+{BS0}),a
		ld	a,(ix+{SST1})
		ld	(ix+{WS1}),a
		ld	(ix+{BS1}),a
		ld	a,(ix+{SSL})
		ld	(ix+{WSL}),a
		ld	(ix+{BSL}),a
		ld	a,(ix+{SPW})
		ld	(ix+{WPW}),a
		ld	(ix+{BPW}),a
		xor	a
		ld	(ix+{WU}),a
		ld	(ix+{WFR}),a
		ld	(ix+{BU}),a
		ld	(ix+{BFR}),a
	WkKor:
		ld	l,(ix+{WP0})
		ld	h,(ix+{WP1})
	WkUgras:
		ld	a,l
		cp	(ix+{WPLO})
		jp	nz,WkNemVeg
		ld	a,h
		cp	(ix+{WPHI})
		jp	z,WkKesz
	WkNemVeg:
		ld	a,(hl)
		cp	$11
		jp	nz,WkNem11
		inc	hl
		ld	a,(hl)
		inc	hl
		ld	h,(hl)
		ld	l,a
		ld	(ix+{WP0}),l
		ld	(ix+{WP1}),h
		jp	WkUgras
	WkNem11:
		cp	$10
		jp	z,WkKesz
		bit	7,a
		jp	z,WkLit
		;	varakozas n kepkocka
		and	$7F
		ld	b,a
		add	a,(ix+{WFR})
		cp	(ix+{QN})
		jp	z,WkVOk
		jp	c,WkVOk
		jp	WkTobb
	WkVOk:
		ld	c,(ix+{WFR})
	WkV:
		ld	a,c
		push	bc
		call	AtQi
		ld	a,{WS0}
		call	AtMezo
		call	AtEq4
		pop	bc
		jp	nz,WkKesz
		inc	c
		djnz	WkV
		ld	(ix+{WFR}),c
		ld	l,(ix+{WP0})
		ld	h,(ix+{WP1})
		inc	hl
		ld	(ix+{WP0}),l
		ld	(ix+{WP1}),h
		jp	WkEgyseg
	WkLit:
		;	SS2 = apply(SS) -> AtLS; p2
		ld	a,(ix+{WS0})
		ld	(AtLS),a
		ld	a,(ix+{WS1})
		ld	(AtLS+1),a
		ld	a,(ix+{WSL})
		ld	(AtLS+2),a
		ld	a,(ix+{WPW})
		ld	(AtLS+3),a
		ld	c,(hl)
		inc	hl
		bit	0,c
		jp	z,WkA1
		ld	a,(hl)
		ld	(AtLS),a
		inc	hl
		ld	a,(hl)
		ld	(AtLS+1),a
		inc	hl
	WkA1:
		bit	1,c
		jp	z,WkA2
		ld	a,(hl)
		inc	hl
		push	hl
		ld	e,a
		rla
		sbc	a,a
		ld	d,a
		ld	hl,(AtLS)
		add	hl,de
		ld	(AtLS),hl
		pop	hl
	WkA2:
		bit	2,c
		jp	z,WkA3
		ld	a,(hl)
		ld	(AtLS+2),a
		inc	hl
	WkA3:
		bit	3,c
		jp	z,WkA4
		ld	a,(hl)
		ld	(AtLS+3),a
		inc	hl
	WkA4:
		ld	a,(ix+{WFR})
		cp	(ix+{QN})
		jp	nc,WkTobb
		push	hl
		call	AtQi
		ld	de,AtLS
		call	AtEq4
		pop	hl
		jp	nz,WkKesz
		ld	(ix+{WP0}),l
		ld	(ix+{WP1}),h
		ld	a,(AtLS)
		ld	(ix+{WS0}),a
		ld	a,(AtLS+1)
		ld	(ix+{WS1}),a
		ld	a,(AtLS+2)
		ld	(ix+{WSL}),a
		ld	a,(AtLS+3)
		ld	(ix+{WPW}),a
		inc	(ix+{WFR})
	WkEgyseg:
		inc	(ix+{WU})
		ld	a,(ix+{WU})
		ld	(ix+{BU}),a
		ld	a,(ix+{WFR})
		ld	(ix+{BFR}),a
		ld	a,(ix+{WS0})
		ld	(ix+{BS0}),a
		ld	a,(ix+{WS1})
		ld	(ix+{BS1}),a
		ld	a,(ix+{WSL})
		ld	(ix+{BSL}),a
		ld	a,(ix+{WPW})
		ld	(ix+{BPW}),a
		ld	a,(ix+{WU})
		cp	255
		jp	z,WkKesz
		jp	WkKor
	WkTobb:
		ld	a,(AtFinal)
		or	a
		jp	nz,WkKesz
		ld	a,(ix+{QN})
		cp	{QMAX}
		jp	nc,WkKesz
		ld	a,1
		ret
	WkKesz:
		ld	(ix+{WACT}),2
		xor	a
		ret

;	------------------------------------------------ AtVege
	AtVege:
		ld	ix,AtHangok
		ld	b,3
	AvH:
		push	bc
		ld	a,1
		ld	(AtFinal),a
		call	AtDont
		ld	a,$11
		ld	(AtBuf),a
		ld	a,(ix+{STLO})
		ld	(AtBuf+1),a
		ld	a,(ix+{STHI})
		ld	(AtBuf+2),a
		ld	b,3
		call	AtIr
		ld	de,{VMERET}
		add	ix,de
		pop	bc
		djnz	AvH
		;	fejlec
		ld	ix,AtHangok
		ld	hl,$5000
		ld	b,3
	AvF:
		ld	a,(ix+{STLO})
		ld	(hl),a
		inc	hl
		ld	a,(ix+{STHI})
		ld	(hl),a
		inc	hl
		ld	de,{VMERET}
		add	ix,de
		djnz	AvF
		ld	a,(AtNext)
		sub	$50
		ld	h,a
		ld	l,0
		ld	(AtHossz),hl
		ret
