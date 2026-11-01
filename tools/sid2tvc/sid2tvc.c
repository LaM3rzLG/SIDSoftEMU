/*
 * sid2tvc - C64 .sid zene -> Videoton TV-Computer (TVC) SIDSoftEMU dal (.STC)
 *
 * Egyetlen, fuggosegek nelkuli C99 forras (Mac, Linux, Windows). Forditas: README.md.
 *
 *   sid2tvc [kapcsolok] fajl.sid
 *     -s N        aldal (alapertelmezes: a .sid kezdo dala); -a = az osszes aldal
 *     -o MAPPA    kimeneti mappa (alapertelmezes: SID_TVC); a dal: MAPPA/<NEV>/SONG<n>.STC
 *     -n NEV      a mappa neve (alapertelmezes: a .sid fajlnevebol, 8 betu)
 *     -w          WAV elonezet is (pontosan ugy, ahogy a TVC-n szol): MAPPA/<NEV>/<nn>.WAV
 *     -f N        hurok nelkul legfeljebb N kepkocka (50/mp, alapertelmezes 30000 = 10 perc)
 *     -m          csak a memoria-hurok (a hang ismetlodeset nem keresi)
 *     -q          csendes (csak hibak)
 *
 * Lepesek (ugyanaz, mint a tools/sid2tvc.py referencia; a Last Ninja-n bajtra egyezik vele):
 *   1. 6502-emulacio: a dal init es play rutinja kepkockankent, a SID-irasok naplozva; memoria-hurok = a teljes
 *      memoria (+ SID-regiszterek) elso ismetlodese (legfeljebb 2 x -f kepkockaig).
 *   2. SID-burkolo (ADSR) a valodi SID-idozitesekkel, fel kepkockanal mintavetelezve.
 *   3. TVC-allapot hangonkent: lepeskoz (5008 Hz-es hang-IT), szelet (hullam + szint 0..5 / negyszog), PW.
 *      Hang-hurok: a hallhato allapot ismetlodese (rovidebb lehet a memoria-huroknal, vagy ott is talal,
 *      ahol a memoria sosem ismetlodik); a kettobol a rovidebb dal nyer.
 *   4. Tomorites hangonkent (rekord / varakozas / REF visszahivatkozas), a hurokpontra ugro VEGE-vel.
 *
 * A .STC formatum (1.1): $FF $FF, 3 x 32 byte info (cim, szerzo, kiadas; 0-val zarva, a TVC-s fontban
 * nem levo jelek szokozre csereve), majd 2 byte hossz (L), a dal $C000 feletti resze, vegul a SONG_BASE..$BFFF resz.
 * (Az 1.0-s fajl az L-lel kezdodik; L sosem $FFFF, igy a TVC mindkettot felismeri.)
 * A dal (SONG_BASE-tol): 6 byte fejlec (a 3 hang folyamanak cime), hangonkent kepkockankent egy rekord:
 *   c = $00..$0F  bit 0 = lepes (2 byte), bit 1 = lepes += elojeles byte, bit 2 = szelet (1 byte: < $80 tablalap
 *                 0..15, >= $80 negyszog, szint = also 3 bit), bit 3 = PW (1 byte)
 *   $80+n         n kepkocka valtozas nelkul;  $10 lo hi n = REF (n rekord a lo/hi cimrol);  $11 lo hi = ugras
 *
 * GPL-3.0-or-later.  SIDSoftEMU projekt, 2026.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <ctype.h>
#include <errno.h>
#include <stdarg.h>
#ifdef _WIN32
#include <direct.h>
#define MKDIR(p) _mkdir(p)
#else
#include <sys/stat.h>
#define MKDIR(p) mkdir((p), 0755)
#endif

#define VERZIO "1.1"

/* ------------------------------------------------------------------ TVC-oldali allandok */
#define SONG_BASE   0x2300              /* a dal cime a TVC-n */
#define TABLE_BASE  0xEF00              /* a hangtablak (a TVC generalja) */
#define SONG_MAX    (TABLE_BASE - SONG_BASE)
#define IT_PER_FRAME 100
#define PAL_CLK     985248.0
#define FRAME_CYC   19656               /* PAL: 312 sor x 63 ciklus */

static const int RATE[16] = {9, 32, 63, 95, 149, 220, 267, 313, 392, 977, 1954, 3126, 3907, 11720, 19532, 31251};

/* a TVC zaj-tablaja (resources/sid_zaj.bin): 256 x 0..15 */
static const uint8_t ZAJ[256] = {
    7,10,6,14,0,15,11,12,12,3,13,10,2,13,7,11,1,10,0,1,1,0,9,3,3,13,12,6,3,11,8,5,
    4,5,7,2,0,7,3,0,4,10,13,0,12,4,13,14,4,10,9,3,15,10,15,2,4,14,4,5,4,13,4,2,
    1,14,0,2,5,8,13,15,7,10,5,8,0,11,8,10,13,13,15,11,1,5,9,2,6,6,2,6,10,14,10,9,
    2,15,12,11,7,9,1,4,0,15,5,10,12,7,15,15,7,0,12,8,0,11,9,15,9,6,1,2,11,13,5,9,
    3,0,3,2,13,1,3,6,14,4,4,12,7,14,8,4,14,9,7,13,5,3,3,4,12,13,2,0,2,0,9,5,
    10,2,10,12,4,15,4,15,15,14,6,12,14,5,12,5,4,14,11,12,1,6,0,8,8,6,7,7,0,6,11,8,
    0,3,3,0,6,3,7,11,15,8,2,14,14,12,3,8,3,10,14,11,8,11,2,6,0,1,0,6,4,12,2,7,
    8,5,5,5,9,14,7,15,2,11,9,11,1,1,0,2,9,15,7,12,0,0,5,11,2,10,15,10,12,7,14,14,
};

static int csendes = 0;
static const char *debug_ki = NULL;   /* -D FAJL: allapotok + nyers dal (hibakereseshez) */
static void info(const char *fmt, ...)
{
    va_list ap;
    if (csendes) return;
    va_start(ap, fmt);
    vprintf(fmt, ap);
    va_end(ap);
}

static void *xmalloc(size_t n)
{
    void *p = calloc(1, n ? n : 1);
    if (!p) { fprintf(stderr, "nincs eleg memoria\n"); exit(2); }
    return p;
}

static void *xrealloc(void *p, size_t n)
{
    p = realloc(p, n);
    if (!p) { fprintf(stderr, "nincs eleg memoria\n"); exit(2); }
    return p;
}

/* ================================================================== .sid fejlec */
typedef struct {
    char magic[5];
    int ver, load, init, play, songs, start;
    uint32_t speed;
    char name[33], author[33], released[33];
    uint8_t *data;
    int len;
} SidFajl;

static int sid_olvas(const char *path, SidFajl *s)
{
    FILE *f = fopen(path, "rb");
    long n;
    uint8_t *b;
    int off;
    if (!f) { fprintf(stderr, "nem nyithato meg: %s\n", path); return 0; }
    fseek(f, 0, SEEK_END);
    n = ftell(f);
    fseek(f, 0, SEEK_SET);
    b = xmalloc(n);
    if (fread(b, 1, n, f) != (size_t)n) { fclose(f); fprintf(stderr, "olvasasi hiba: %s\n", path); return 0; }
    fclose(f);
    if (n < 0x76 || (memcmp(b, "PSID", 4) && memcmp(b, "RSID", 4))) {
        fprintf(stderr, "nem PSID/RSID fajl: %s\n", path);
        return 0;
    }
    memcpy(s->magic, b, 4);
    s->magic[4] = 0;
    s->ver = b[5];
    off = (b[6] << 8) | b[7];
    s->load = (b[8] << 8) | b[9];
    s->init = (b[10] << 8) | b[11];
    s->play = (b[12] << 8) | b[13];
    s->songs = (b[14] << 8) | b[15];
    s->start = (b[16] << 8) | b[17];
    s->speed = ((uint32_t)b[18] << 24) | ((uint32_t)b[19] << 16) | ((uint32_t)b[20] << 8) | b[21];
    memcpy(s->name, b + 22, 32); s->name[32] = 0;
    memcpy(s->author, b + 54, 32); s->author[32] = 0;
    memcpy(s->released, b + 86, 32); s->released[32] = 0;
    s->data = b + off;
    s->len = (int)(n - off);
    if (s->load == 0) {
        s->load = s->data[0] | (s->data[1] << 8);
        s->data += 2;
        s->len -= 2;
    }
    if (s->init == 0) s->init = s->load;
    return 1;
}

/* ================================================================== 6502 (a tools/m6502.py masa + illegalis utasitasok) */
typedef struct { uint8_t r, v; } Iras;

typedef struct {
    uint8_t m[65536];
    uint8_t a, x, y, sp, c, z, i, d, v, n;
    uint16_t pc;
    uint8_t raster;
    uint8_t sid_regs[32];
    uint32_t rnd;
    /* az aktualis kepkocka SID-irasai */
    Iras *log;
    int nlog, caplog;
    int hiba;                           /* 1 = ismeretlen/JAM utasitas, 2 = tul hosszu hivas */
    uint16_t hibapc;
    uint8_t hibaop;
} Cpu;

static uint8_t rnd8(Cpu *c)
{
    c->rnd = c->rnd * 1103515245u + 12345u;
    return (uint8_t)(c->rnd >> 16);
}

static uint8_t rd(Cpu *c, uint16_t a)
{
    if (a >= 0xD000 && a < 0xE000) {
        if (a == 0xD012) { c->raster++; return c->raster; }
        if (a == 0xD011) return 0x1B;
        if (a >= 0xD400 && a < 0xD800) {
            if ((a & 0x1F) == 0x1B) return rnd8(c);
            return 0;
        }
    }
    return c->m[a];
}

static void wr(Cpu *c, uint16_t a, uint8_t v)
{
    if (a >= 0xD400 && a < 0xD800) {
        int r = a & 0x1F;
        c->sid_regs[r] = v;
        if (c->nlog == c->caplog) {
            c->caplog = c->caplog ? c->caplog * 2 : 64;
            c->log = xrealloc(c->log, c->caplog * sizeof(Iras));
        }
        c->log[c->nlog].r = (uint8_t)r;
        c->log[c->nlog].v = v;
        c->nlog++;
        return;
    }
    c->m[a] = v;
}

static void push(Cpu *c, uint8_t v) { c->m[0x100 + c->sp] = v; c->sp--; }
static uint8_t pull(Cpu *c) { c->sp++; return c->m[0x100 + c->sp]; }
static uint8_t get_p(Cpu *c)
{
    return (uint8_t)((c->n << 7) | (c->v << 6) | 0x20 | (c->d << 3) | (c->i << 2) | (c->z << 1) | c->c);
}
static void set_p(Cpu *c, uint8_t p)
{
    c->n = (p >> 7) & 1; c->v = (p >> 6) & 1; c->d = (p >> 3) & 1;
    c->i = (p >> 2) & 1; c->z = (p >> 1) & 1; c->c = p & 1;
}
static uint8_t nz(Cpu *c, uint8_t v) { c->n = (v >> 7) & 1; c->z = v == 0; return v; }
static uint8_t fetch(Cpu *c) { uint8_t v = c->m[c->pc]; c->pc++; return v; }
static uint16_t fetchw(Cpu *c) { uint16_t lo = fetch(c); return (uint16_t)(lo | (fetch(c) << 8)); }

enum { IMP, ACC, IMM, ZP, ZPX, ZPY, ABS, ABX, ABY, IZX, IZY, REL, IND };

static uint16_t ea(Cpu *c, int mode)
{
    uint8_t z;
    switch (mode) {
    case ZP: return fetch(c);
    case ZPX: return (uint8_t)(fetch(c) + c->x);
    case ZPY: return (uint8_t)(fetch(c) + c->y);
    case ABS: return fetchw(c);
    case ABX: return (uint16_t)(fetchw(c) + c->x);
    case ABY: return (uint16_t)(fetchw(c) + c->y);
    case IZX: z = (uint8_t)(fetch(c) + c->x); return (uint16_t)(c->m[z] | (c->m[(uint8_t)(z + 1)] << 8));
    case IZY: z = fetch(c); return (uint16_t)((c->m[z] | (c->m[(uint8_t)(z + 1)] << 8)) + c->y);
    }
    return 0;
}

static void adc(Cpu *c, uint8_t v)
{
    if (c->d) {
        int lo = (c->a & 0xF) + (v & 0xF) + c->c;
        int hi = (c->a >> 4) + (v >> 4);
        if (lo > 9) { lo += 6; hi += 1; }
        c->z = ((c->a + v + c->c) & 0xFF) == 0;
        c->n = (hi >> 3) & 1;
        c->v = (~(c->a ^ v) & (c->a ^ (hi << 4)) & 0x80) ? 1 : 0;
        if (hi > 9) hi += 6;
        c->c = hi > 15;
        c->a = (uint8_t)((hi << 4) | (lo & 0xF));
        return;
    }
    {
        int r = c->a + v + c->c;
        c->v = (~(c->a ^ v) & (c->a ^ r) & 0x80) ? 1 : 0;
        c->c = r > 0xFF;
        c->a = nz(c, (uint8_t)r);
    }
}

static void sbc(Cpu *c, uint8_t v)
{
    int r = c->a - v - (1 - c->c);
    if (c->d) {
        int lo = (c->a & 0xF) - (v & 0xF) - (1 - c->c);
        int hi = (c->a >> 4) - (v >> 4);
        if (lo < 0) { lo -= 6; hi -= 1; }
        if (hi < 0) hi -= 6;
        c->v = ((c->a ^ v) & (c->a ^ r) & 0x80) ? 1 : 0;
        c->c = r >= 0;
        nz(c, (uint8_t)r);
        c->a = (uint8_t)((hi << 4) | (lo & 0xF));
        return;
    }
    c->v = ((c->a ^ v) & (c->a ^ r) & 0x80) ? 1 : 0;
    c->c = r >= 0;
    c->a = nz(c, (uint8_t)r);
}

static void cmp(Cpu *c, uint8_t reg, uint8_t v) { int r = reg - v; c->c = r >= 0; nz(c, (uint8_t)r); }
static void branch(Cpu *c, int cond) { int8_t off = (int8_t)fetch(c); if (cond) c->pc = (uint16_t)(c->pc + off); }

static uint8_t asl_(Cpu *c, uint8_t v) { c->c = v >> 7; return nz(c, (uint8_t)(v << 1)); }
static uint8_t lsr_(Cpu *c, uint8_t v) { c->c = v & 1; return nz(c, v >> 1); }
static uint8_t rol_(Cpu *c, uint8_t v) { uint8_t r = (uint8_t)((v << 1) | c->c); c->c = v >> 7; return nz(c, r); }
static uint8_t ror_(Cpu *c, uint8_t v) { uint8_t r = (uint8_t)((v >> 1) | (c->c << 7)); c->c = v & 1; return nz(c, r); }

/* utasitas-tablazat: muvelet + cimzes (NMOS 6510, a stabil illegalis utasitasokkal) */
enum {
    BRK, ORA, JAM, SLO, NOP, ASL, PHP, ANC, BPL, CLC, JSR, AND, RLA, BIT, ROL, PLP, BMI, SEC, RTI, EOR, SRE,
    LSR, PHA, ALR, JMP, BVC, CLI, RTS, ADC, RRA, ROR, PLA, ARR, BVS, SEI, STA, SAX, STY, STX, DEY, TXA, ANE,
    BCC, SHA, TYA, TXS, TAS, SHY, SHX, LDY, LDA, LDX, LAX, TAY, TAX, LXA, BCS, CLV, TSX, LAS, CPY, CMP, DCP,
    DEC, INY, DEX, SBX, BNE, CLD, CPX, SBC, ISC, INC, INX, BEQ, SED
};
static const uint8_t OPM[256][2] = {
    {BRK,IMP},{ORA,IZX},{JAM,IMP},{SLO,IZX},{NOP,ZP},{ORA,ZP},{ASL,ZP},{SLO,ZP},{PHP,IMP},{ORA,IMM},{ASL,ACC},{ANC,IMM},{NOP,ABS},{ORA,ABS},{ASL,ABS},{SLO,ABS},
    {BPL,REL},{ORA,IZY},{JAM,IMP},{SLO,IZY},{NOP,ZPX},{ORA,ZPX},{ASL,ZPX},{SLO,ZPX},{CLC,IMP},{ORA,ABY},{NOP,IMP},{SLO,ABY},{NOP,ABX},{ORA,ABX},{ASL,ABX},{SLO,ABX},
    {JSR,ABS},{AND,IZX},{JAM,IMP},{RLA,IZX},{BIT,ZP},{AND,ZP},{ROL,ZP},{RLA,ZP},{PLP,IMP},{AND,IMM},{ROL,ACC},{ANC,IMM},{BIT,ABS},{AND,ABS},{ROL,ABS},{RLA,ABS},
    {BMI,REL},{AND,IZY},{JAM,IMP},{RLA,IZY},{NOP,ZPX},{AND,ZPX},{ROL,ZPX},{RLA,ZPX},{SEC,IMP},{AND,ABY},{NOP,IMP},{RLA,ABY},{NOP,ABX},{AND,ABX},{ROL,ABX},{RLA,ABX},
    {RTI,IMP},{EOR,IZX},{JAM,IMP},{SRE,IZX},{NOP,ZP},{EOR,ZP},{LSR,ZP},{SRE,ZP},{PHA,IMP},{EOR,IMM},{LSR,ACC},{ALR,IMM},{JMP,ABS},{EOR,ABS},{LSR,ABS},{SRE,ABS},
    {BVC,REL},{EOR,IZY},{JAM,IMP},{SRE,IZY},{NOP,ZPX},{EOR,ZPX},{LSR,ZPX},{SRE,ZPX},{CLI,IMP},{EOR,ABY},{NOP,IMP},{SRE,ABY},{NOP,ABX},{EOR,ABX},{LSR,ABX},{SRE,ABX},
    {RTS,IMP},{ADC,IZX},{JAM,IMP},{RRA,IZX},{NOP,ZP},{ADC,ZP},{ROR,ZP},{RRA,ZP},{PLA,IMP},{ADC,IMM},{ROR,ACC},{ARR,IMM},{JMP,IND},{ADC,ABS},{ROR,ABS},{RRA,ABS},
    {BVS,REL},{ADC,IZY},{JAM,IMP},{RRA,IZY},{NOP,ZPX},{ADC,ZPX},{ROR,ZPX},{RRA,ZPX},{SEI,IMP},{ADC,ABY},{NOP,IMP},{RRA,ABY},{NOP,ABX},{ADC,ABX},{ROR,ABX},{RRA,ABX},
    {NOP,IMM},{STA,IZX},{NOP,IMM},{SAX,IZX},{STY,ZP},{STA,ZP},{STX,ZP},{SAX,ZP},{DEY,IMP},{NOP,IMM},{TXA,IMP},{ANE,IMM},{STY,ABS},{STA,ABS},{STX,ABS},{SAX,ABS},
    {BCC,REL},{STA,IZY},{JAM,IMP},{SHA,IZY},{STY,ZPX},{STA,ZPX},{STX,ZPY},{SAX,ZPY},{TYA,IMP},{STA,ABY},{TXS,IMP},{TAS,ABY},{SHY,ABX},{STA,ABX},{SHX,ABY},{SHA,ABY},
    {LDY,IMM},{LDA,IZX},{LDX,IMM},{LAX,IZX},{LDY,ZP},{LDA,ZP},{LDX,ZP},{LAX,ZP},{TAY,IMP},{LDA,IMM},{TAX,IMP},{LXA,IMM},{LDY,ABS},{LDA,ABS},{LDX,ABS},{LAX,ABS},
    {BCS,REL},{LDA,IZY},{JAM,IMP},{LAX,IZY},{LDY,ZPX},{LDA,ZPX},{LDX,ZPY},{LAX,ZPY},{CLV,IMP},{LDA,ABY},{TSX,IMP},{LAS,ABY},{LDY,ABX},{LDA,ABX},{LDX,ABY},{LAX,ABY},
    {CPY,IMM},{CMP,IZX},{NOP,IMM},{DCP,IZX},{CPY,ZP},{CMP,ZP},{DEC,ZP},{DCP,ZP},{INY,IMP},{CMP,IMM},{DEX,IMP},{SBX,IMM},{CPY,ABS},{CMP,ABS},{DEC,ABS},{DCP,ABS},
    {BNE,REL},{CMP,IZY},{JAM,IMP},{DCP,IZY},{NOP,ZPX},{CMP,ZPX},{DEC,ZPX},{DCP,ZPX},{CLD,IMP},{CMP,ABY},{NOP,IMP},{DCP,ABY},{NOP,ABX},{CMP,ABX},{DEC,ABX},{DCP,ABX},
    {CPX,IMM},{SBC,IZX},{NOP,IMM},{ISC,IZX},{CPX,ZP},{SBC,ZP},{INC,ZP},{ISC,ZP},{INX,IMP},{SBC,IMM},{NOP,IMP},{SBC,IMM},{CPX,ABS},{SBC,ABS},{INC,ABS},{ISC,ABS},
    {BEQ,REL},{SBC,IZY},{JAM,IMP},{ISC,IZY},{NOP,ZPX},{SBC,ZPX},{INC,ZPX},{ISC,ZPX},{SED,IMP},{SBC,ABY},{NOP,IMP},{ISC,ABY},{NOP,ABX},{SBC,ABX},{INC,ABX},{ISC,ABX},
};

static uint8_t operand(Cpu *c, int mode) { return mode == IMM ? fetch(c) : rd(c, ea(c, mode)); }

/* read-modify-write: a cim, az uj ertek; ACC eseten az A */
#define RMW(expr) do { if (mode == ACC) { uint8_t v = c->a; c->a = (expr); } \
    else { uint16_t ad = ea(c, mode); uint8_t v = rd(c, ad); wr(c, ad, (expr)); } } while (0)

static void lepes(Cpu *c)
{
    uint16_t pc0 = c->pc;
    uint8_t op = fetch(c);
    int mn = OPM[op][0], mode = OPM[op][1];
    uint16_t ad;
    uint8_t v, t;
    switch (mn) {
    case LDA: c->a = nz(c, operand(c, mode)); break;
    case LDX: c->x = nz(c, operand(c, mode)); break;
    case LDY: c->y = nz(c, operand(c, mode)); break;
    case LAX: c->a = c->x = nz(c, operand(c, mode)); break;
    case STA: wr(c, ea(c, mode), c->a); break;
    case STX: wr(c, ea(c, mode), c->x); break;
    case STY: wr(c, ea(c, mode), c->y); break;
    case SAX: wr(c, ea(c, mode), c->a & c->x); break;
    case ORA: c->a = nz(c, c->a | operand(c, mode)); break;
    case AND: c->a = nz(c, c->a & operand(c, mode)); break;
    case EOR: c->a = nz(c, c->a ^ operand(c, mode)); break;
    case ADC: adc(c, operand(c, mode)); break;
    case SBC: sbc(c, operand(c, mode)); break;
    case CMP: cmp(c, c->a, operand(c, mode)); break;
    case CPX: cmp(c, c->x, operand(c, mode)); break;
    case CPY: cmp(c, c->y, operand(c, mode)); break;
    case BIT: v = operand(c, mode); c->z = (c->a & v) == 0; c->n = v >> 7; c->v = (v >> 6) & 1; break;
    case ASL: RMW(asl_(c, v)); break;
    case LSR: RMW(lsr_(c, v)); break;
    case ROL: RMW(rol_(c, v)); break;
    case ROR: RMW(ror_(c, v)); break;
    case INC: RMW(nz(c, (uint8_t)(v + 1))); break;
    case DEC: RMW(nz(c, (uint8_t)(v - 1))); break;
    case SLO: ad = ea(c, mode); v = asl_(c, rd(c, ad)); wr(c, ad, v); c->a = nz(c, c->a | v); break;
    case RLA: ad = ea(c, mode); v = rol_(c, rd(c, ad)); wr(c, ad, v); c->a = nz(c, c->a & v); break;
    case SRE: ad = ea(c, mode); v = lsr_(c, rd(c, ad)); wr(c, ad, v); c->a = nz(c, c->a ^ v); break;
    case RRA: ad = ea(c, mode); v = ror_(c, rd(c, ad)); wr(c, ad, v); adc(c, v); break;
    case DCP: ad = ea(c, mode); v = (uint8_t)(rd(c, ad) - 1); wr(c, ad, v); cmp(c, c->a, v); break;
    case ISC: ad = ea(c, mode); v = (uint8_t)(rd(c, ad) + 1); wr(c, ad, v); sbc(c, v); break;
    case ANC: c->a = nz(c, c->a & fetch(c)); c->c = c->n; break;
    case ALR: c->a = lsr_(c, c->a & fetch(c)); break;
    case ARR: c->a = c->a & fetch(c); c->a = ror_(c, c->a); c->c = (c->a >> 6) & 1; c->v = ((c->a >> 6) ^ (c->a >> 5)) & 1; break;
    case SBX: { int r = (c->a & c->x) - fetch(c); c->c = r >= 0; c->x = nz(c, (uint8_t)r); } break;
    case ANE: c->a = nz(c, (c->a | 0xEE) & c->x & fetch(c)); break;
    case LXA: c->a = c->x = nz(c, (c->a | 0xEE) & fetch(c)); break;
    case LAS: t = (uint8_t)(rd(c, ea(c, mode)) & c->sp); c->a = c->x = c->sp = nz(c, t); break;
    case SHA: ad = ea(c, mode); wr(c, ad, (uint8_t)(c->a & c->x & ((ad >> 8) + 1))); break;
    case SHX: ad = ea(c, mode); wr(c, ad, (uint8_t)(c->x & ((ad >> 8) + 1))); break;
    case SHY: ad = ea(c, mode); wr(c, ad, (uint8_t)(c->y & ((ad >> 8) + 1))); break;
    case TAS: ad = ea(c, mode); c->sp = c->a & c->x; wr(c, ad, (uint8_t)(c->sp & ((ad >> 8) + 1))); break;
    case NOP: if (mode != IMP) { if (mode == IMM) fetch(c); else (void)rd(c, ea(c, mode)); } break;
    case INX: c->x = nz(c, (uint8_t)(c->x + 1)); break;
    case DEX: c->x = nz(c, (uint8_t)(c->x - 1)); break;
    case INY: c->y = nz(c, (uint8_t)(c->y + 1)); break;
    case DEY: c->y = nz(c, (uint8_t)(c->y - 1)); break;
    case TAX: c->x = nz(c, c->a); break;
    case TXA: c->a = nz(c, c->x); break;
    case TAY: c->y = nz(c, c->a); break;
    case TYA: c->a = nz(c, c->y); break;
    case TSX: c->x = nz(c, c->sp); break;
    case TXS: c->sp = c->x; break;
    case PHA: push(c, c->a); break;
    case PLA: c->a = nz(c, pull(c)); break;
    case PHP: push(c, get_p(c) | 0x10); break;
    case PLP: set_p(c, pull(c)); break;
    case CLC: c->c = 0; break;
    case SEC: c->c = 1; break;
    case CLI: c->i = 0; break;
    case SEI: c->i = 1; break;
    case CLV: c->v = 0; break;
    case CLD: c->d = 0; break;
    case SED: c->d = 1; break;
    case JSR: ad = fetchw(c); { uint16_t r = (uint16_t)(c->pc - 1); push(c, r >> 8); push(c, r & 0xFF); } c->pc = ad; break;
    case RTS: { uint16_t lo = pull(c); c->pc = (uint16_t)((lo | (pull(c) << 8)) + 1); } break;
    case RTI: set_p(c, pull(c)); { uint16_t lo = pull(c); c->pc = (uint16_t)(lo | (pull(c) << 8)); } break;
    case JMP:
        if (mode == ABS) c->pc = fetchw(c);
        else { ad = fetchw(c); c->pc = (uint16_t)(c->m[ad] | (c->m[(ad & 0xFF00) | ((ad + 1) & 0xFF)] << 8)); }
        break;
    case BPL: branch(c, !c->n); break;
    case BMI: branch(c, c->n); break;
    case BVC: branch(c, !c->v); break;
    case BVS: branch(c, c->v); break;
    case BCC: branch(c, !c->c); break;
    case BCS: branch(c, c->c); break;
    case BNE: branch(c, !c->z); break;
    case BEQ: branch(c, c->z); break;
    default:                            /* BRK, JAM */
        c->hiba = 1; c->hibapc = pc0; c->hibaop = op;
    }
}

#define SENT 0xFFF0
/* JSR addr; addig fut, amig a visszateres a szentinelre er. 0 = rendben */
static int hivas(Cpu *c, uint16_t addr, uint8_t a, long max)
{
    long n = 0;
    uint16_t ret = SENT - 1;
    c->a = a; c->x = 0; c->y = 0;
    push(c, ret >> 8);
    push(c, ret & 0xFF);
    c->pc = addr;
    while (c->pc != SENT) {
        lepes(c);
        if (c->hiba) return 1;
        if (++n > max) { c->hiba = 2; c->hibapc = c->pc; return 2; }
    }
    return 0;
}

/* IRQ-rutin hivasa (play = 0 eseten): a KERNAL-belepes masa ($0314: A, X, Y a veremre), RTI-vel a szentinelre */
static int irq_hivas(Cpu *c, uint16_t addr, int kernal, long max)
{
    long n = 0;
    push(c, SENT >> 8);
    push(c, SENT & 0xFF);
    push(c, get_p(c) & ~0x10);
    if (kernal) { push(c, c->a); push(c, c->x); push(c, c->y); }
    c->pc = addr;
    while (c->pc != SENT) {
        lepes(c);
        if (c->hiba) return 1;
        if (++n > max) { c->hiba = 2; c->hibapc = c->pc; return 2; }
    }
    return 0;
}

/* ================================================================== 1. dump: kepkockankenti SID-irasok + hurok */
typedef struct { Iras *w; int n; } Kep;
typedef struct { Kep *k; int n, loop; } Dump;

typedef struct { uint64_t h1, h2; int fr; } HSlot;

static void hash_mem(Cpu *c, uint64_t *o1, uint64_t *o2)
{
    uint64_t h1 = 1469598103934665603ULL, h2 = 0x9E3779B97F4A7C15ULL;
    int i;
    for (i = 0; i < 65536; i++) {
        h1 = (h1 ^ c->m[i]) * 1099511628211ULL;
        h2 = (h2 + c->m[i] + 1) * 0xC2B2AE3D27D4EB4FULL;
        h2 ^= h2 >> 29;
    }
    for (i = 0; i < 32; i++) {
        h1 = (h1 ^ c->sid_regs[i]) * 1099511628211ULL;
        h2 = (h2 + c->sid_regs[i] + 1) * 0xC2B2AE3D27D4EB4FULL;
        h2 ^= h2 >> 29;
    }
    *o1 = h1; *o2 = h2;
}

static int dump(const SidFajl *s, int song, int maxf, Dump *dp, char *hibaszoveg)
{
    Cpu *c = xmalloc(sizeof(Cpu));
    int fr, init_n;
    Iras *init_w;
    HSlot *tab;
    int tabmeret = 1;
    uint16_t play = (uint16_t)s->play;
    int irq_kernal = 0;
    while (tabmeret < maxf * 2) tabmeret <<= 1;
    tab = xmalloc(sizeof(HSlot) * tabmeret);
    for (fr = 0; fr < tabmeret; fr++) tab[fr].fr = -1;
    memcpy(c->m + s->load, s->data, (size_t)((s->load + s->len > 65536) ? 65536 - s->load : s->len));
    c->m[0x01] = 0x37;
    c->sp = 0xFF;
    c->rnd = 1;
    if (hivas(c, (uint16_t)s->init, (uint8_t)(song - 1), 2000000)) {
        if (c->hiba == 2 && (s->play == 0 || !memcmp(s->magic, "RSID", 4))) {
            /* az init nem ter vissza (RSID foprogram): eleg, ha az IRQ-t beallitotta */
            c->hiba = 0;
            c->sp = 0xFF;
        } else {
            snprintf(hibaszoveg, 256, "az init hibas utasitasra futott: $%02X a $%04X cimen", c->hibaop, c->hibapc);
            return 0;
        }
    }
    if (play == 0) {
        /* a dal IRQ-rutint allitott be: $0314 (KERNAL bent) vagy $FFFE */
        uint16_t v314 = (uint16_t)(c->m[0x314] | (c->m[0x315] << 8));
        uint16_t vfffe = (uint16_t)(c->m[0xFFFE] | (c->m[0xFFFF] << 8));
        if ((c->m[1] & 3) != 0 && v314 >= 0x0400 && v314 < 0xA000) { play = v314; irq_kernal = 1; }
        else if (vfffe) { play = vfffe; irq_kernal = 0; }
        if (play == 0) { snprintf(hibaszoveg, 256, "a play cim 0, es IRQ-vektort sem talaltam"); return 0; }
        /* a KERNAL IRQ-vege ($EA31, $EA81, $FEBC): Y, X, A vissza, RTI */
        {
            static const uint8_t vege[] = {0x68, 0xA8, 0x68, 0xAA, 0x68, 0x40};
            memcpy(c->m + 0xEA81, vege, sizeof(vege));
            memcpy(c->m + 0xFEBC, vege, sizeof(vege));
            c->m[0xEA31] = 0x4C; c->m[0xEA32] = 0x81; c->m[0xEA33] = 0xEA;
        }
        info("  IRQ-s dal: play = $%04X (%s)\n", play, irq_kernal ? "$0314" : "$FFFE");
    }
    init_n = c->nlog;
    init_w = xmalloc(sizeof(Iras) * (init_n + 1));
    memcpy(init_w, c->log, sizeof(Iras) * init_n);
    dp->k = xmalloc(sizeof(Kep) * maxf);
    dp->n = 0;
    dp->loop = -1;
    for (fr = 0; fr < maxf; fr++) {
        uint64_t h1, h2;
        int idx, r;
        hash_mem(c, &h1, &h2);
        idx = (int)(h1 & (tabmeret - 1));
        while (tab[idx].fr >= 0) {
            if (tab[idx].h1 == h1 && tab[idx].h2 == h2) { dp->loop = tab[idx].fr; break; }
            idx = (idx + 1) & (tabmeret - 1);
        }
        if (dp->loop >= 0) break;
        tab[idx].h1 = h1; tab[idx].h2 = h2; tab[idx].fr = fr;
        c->nlog = 0;
        if (s->play == 0) r = irq_hivas(c, play, irq_kernal, 2000000);
        else r = hivas(c, play, 0, 2000000);
        if (r) {
            snprintf(hibaszoveg, 256, "a play hibas utasitasra futott: $%02X a $%04X cimen (%d. kepkocka)", c->hibaop, c->hibapc, fr);
            return 0;
        }
        {
            Kep *k = &dp->k[dp->n++];
            int extra = (fr == 0) ? init_n : 0;
            k->n = c->nlog + extra;
            k->w = xmalloc(sizeof(Iras) * (k->n + 1));
            if (extra) memcpy(k->w, init_w, sizeof(Iras) * init_n);
            memcpy(k->w + extra, c->log, sizeof(Iras) * c->nlog);
        }
    }
    free(tab);
    free(init_w);
    free(c->log);
    free(c);
    return 1;
}

static void w16(FILE *f, int v) { fputc(v & 0xFF, f); fputc((v >> 8) & 0xFF, f); }

/* egy info-mezo (32 byte): 31 jel + 0. Megmarad: ASCII 32..122 es a Latin-1 ekezetes betuk (>= $C0, a TVC-s Ir16
   ezeket ismeri); minden mas -> szokoz. */
static void info_ir(FILE *f, const char *t)
{
    unsigned char o[32];
    int i;
    memset(o, 0, sizeof(o));
    for (i = 0; i < 31 && t[i]; i++) {
        unsigned char c = (unsigned char)t[i];
        o[i] = ((c >= 32 && c <= 122) || c >= 0xC0) ? c : ' ';
    }
    fwrite(o, 1, 32, f);
}

/* ================================================================== 2. SID-burkolo */
typedef struct { int lvl, state, rc, ec, a, d, s, r, gate; } Env;   /* state: 0 A, 1 D, 2 R */

static int exp_period(int l)
{
    return l >= 93 ? 1 : l >= 54 ? 2 : l >= 26 ? 4 : l >= 14 ? 8 : l >= 6 ? 16 : 30;
}

static void env_control(Env *e, int ctrl)
{
    int g = ctrl & 1;
    if (g && !e->gate) e->state = 0;
    else if (!g && e->gate) e->state = 2;
    e->gate = g;
}

static void env_run(Env *e, int cyc)
{
    while (cyc > 0) {
        int rate = RATE[e->state == 0 ? e->a : e->state == 1 ? e->d : e->r];
        int need = rate - e->rc;
        if (need > cyc) { e->rc += cyc; return; }
        cyc -= need;
        e->rc = 0;
        if (e->state == 0) {
            e->lvl++;
            if (e->lvl >= 255) { e->lvl = 255; e->state = 1; }
            continue;
        }
        if (e->state == 1 && e->lvl <= e->s * 17) continue;
        if (e->lvl == 0) continue;
        e->ec++;
        if (e->ec >= exp_period(e->lvl)) { e->ec = 0; e->lvl--; }
    }
}

/* ================================================================== 3. TVC-allapot */
typedef struct { uint16_t st; uint8_t sl, pw; } All;
static int all_eq(All a, All b) { return a.st == b.st && a.sl == b.sl && a.pw == b.pw; }

static double STEP_MUL;

static All *tvc_allapotok(const Dump *dp)
{
    uint8_t regs[32];
    Env env[3];
    All prev[3];
    All *T = xmalloc(sizeof(All) * 3 * (dp->n + 1));
    int f, v, i;
    memset(regs, 0, sizeof(regs));
    memset(env, 0, sizeof(env));
    for (v = 0; v < 3; v++) { env[v].state = 2; prev[v].st = 0; prev[v].sl = 0; prev[v].pw = 128; }
    for (f = 0; f < dp->n; f++) {
        int mid[3], vol;
        for (i = 0; i < dp->k[f].n; i++) {
            int r = dp->k[f].w[i].r, val = dp->k[f].w[i].v;
            regs[r] = (uint8_t)val;
            if (r < 21) {
                int vo = r / 7, k = r % 7;
                Env *e = &env[vo];
                if (k == 4) env_control(e, val);
                else if (k == 5) { e->a = val >> 4; e->d = val & 15; }
                else if (k == 6) { e->s = val >> 4; e->r = val & 15; }
            }
        }
        for (v = 0; v < 3; v++) {
            env_run(&env[v], FRAME_CYC / 2);
            mid[v] = env[v].lvl;
            env_run(&env[v], FRAME_CYC - FRAME_CYC / 2);
        }
        vol = regs[24] & 15;
        for (v = 0; v < 3; v++) {
            int b = v * 7;
            int F = regs[b] | (regs[b + 1] << 8);
            int ctrl = regs[b + 4];
            int pw = regs[b + 2] | ((regs[b + 3] & 15) << 8);
            int wave = ctrl >> 4;
            int amp = (mid[v] * vol * 2 + 765) / 1530;          /* = int(lvl/255 * vol/15 * 5 + 0.5) */
            volatile double t = F * STEP_MUL;
            int step;
            All cur = prev[v];
            t = t + 0.5;
            step = (int)t;
            if (step > 0xFFFF) step = 0xFFFF;
            if ((ctrl & 8) || wave == 0) amp = 0;
            if (amp == 0) {
                cur.sl = 0;
            } else {
                if (wave & 8) { cur.sl = (uint8_t)(1 + 2 * 5 + amp - 1); step = step / 16; if (step < 1) step = 1; }
                else if (wave & 4) { cur.sl = (uint8_t)(0x80 | amp); cur.pw = (uint8_t)(pw >> 4); }
                else if (wave & 2) cur.sl = (uint8_t)(1 + amp - 1);
                else cur.sl = (uint8_t)(1 + 5 + amp - 1);
                cur.st = (uint16_t)step;
            }
            T[f * 3 + v] = cur;
            prev[v] = cur;
        }
    }
    return T;
}

/* ================================================================== 3b. hurok a HANGBOL (a TVC-allapot ismetlodese)
   A memoria-hurok (1. lepes) csak akkor talal, ha a teljes C64-memoria pontosan ismetlodik; sok lejatszo
   kozben szamlalot leptet, igy a hang mar ismetlodik, a memoria meg nem. Itt azt keressuk, ahol a hallhato
   allapot (3 hang: lepes, szelet, PW) ismetlodik: a legkisebb L + P, amire T[f] = T[f + P] minden f >= L-re.
   - Ha van memoria-hurok: a dal attol fogva pontosan periodikus, ezert a sorozatot kiterjesztjuk (a hurok
     masodik koreig), es az eredmeny biztos (a legkisebb periodus a memoria-periodus osztoja).
   - Ha nincs: csak a 10 perces mintabol dontunk, ezert legalabb 2 teljes ismetles es 30 s egyezes kell
     (kulonben egy kitartott hang a vegen hamis hurkot adna).
   Eredmeny: *pN = L + P (ennyi kepkockat kodolunk), *pLoop = L; 1, ha rovidebb lett, mint a memoria szerint. */
static int frame_eq(const All *T, int a, int b)
{
    return all_eq(T[a * 3], T[b * 3]) && all_eq(T[a * 3 + 1], T[b * 3 + 1]) && all_eq(T[a * 3 + 2], T[b * 3 + 2]);
}

static int hang_hurok(const All *T, int *pN, int *pLoop)
{
    int N = *pN, Lm = *pLoop, Next, minfarok, P, f;
    int best = N, bestL = Lm;
    All *E;
    if (Lm >= 0) { int Pm = N - Lm; Next = Lm + 2 * Pm; minfarok = 0; }
    else { Next = N; minfarok = 1500; }
    E = xmalloc(sizeof(All) * 3 * (Next + 1));
    for (f = 0; f < Next; f++) {
        int src = f < N ? f : Lm + (f - N);
        memcpy(&E[f * 3], &T[src * 3], sizeof(All) * 3);
    }
    for (P = 1; P <= Next / 2; P++) {
        int L, farok;
        f = Next - P - 1;
        while (f >= 0 && frame_eq(E, f, f + P)) f--;
        L = f + 1;
        farok = Next - L;
        if (farok < 2 * P || farok < minfarok) continue;
        if (L + P < best) { best = L + P; bestL = L; }
    }
    free(E);
    if (best < N || (Lm < 0 && bestL >= 0)) { *pN = best; *pLoop = bestL; return 1; }
    return 0;
}

/* ================================================================== 4. kodolas (a sid2tvc.py encode_voice masa) */
typedef struct { uint8_t *b; int n, cap; } Buf;
static void bput(Buf *b, int v)
{
    if (b->n == b->cap) { b->cap = b->cap ? b->cap * 2 : 4096; b->b = xrealloc(b->b, b->cap); }
    b->b[b->n++] = (uint8_t)v;
}

static int lit_bytes(All S, All T, int full, uint8_t *out)
{
    int c = 0, n = 1;
    if (full || T.st != S.st) {
        int dl = (T.st - S.st) & 0xFFFF;
        if (!full && (dl < 128 || dl >= 0x10000 - 128)) { c |= 2; out[n++] = (uint8_t)(dl & 0xFF); }
        else { c |= 1; out[n++] = (uint8_t)(T.st & 0xFF); out[n++] = (uint8_t)(T.st >> 8); }
    }
    if (full || T.sl != S.sl) { c |= 4; out[n++] = T.sl; }
    if (full || T.pw != S.pw) { c |= 8; out[n++] = T.pw; }
    out[0] = (uint8_t)c;
    return n;
}

static All apply_lit(All S, const uint8_t *b, int *p)
{
    int c = b[(*p)++];
    if (c & 1) { S.st = (uint16_t)(b[*p] | (b[*p + 1] << 8)); *p += 2; }
    if (c & 2) { int d = b[(*p)++]; S.st = (uint16_t)((S.st + d - (d > 127 ? 256 : 0)) & 0xFFFF); }
    if (c & 4) S.sl = b[(*p)++];
    if (c & 8) S.pw = b[(*p)++];
    return S;
}

/* allapot -> egysegek listaja (hash) */
typedef struct { int *u; int n, cap; All key; int used; } Lista;
typedef struct { Lista *t; int meret; } Index;

static unsigned all_hash(All a) { return (unsigned)(a.st * 2654435761u) ^ (unsigned)(a.sl * 40503u) ^ (unsigned)(a.pw * 97u); }

static Lista *index_get(Index *ix, All k, int letrehoz)
{
    unsigned h = all_hash(k) & (ix->meret - 1);
    while (ix->t[h].used) {
        if (all_eq(ix->t[h].key, k)) return &ix->t[h];
        h = (h + 1) & (ix->meret - 1);
    }
    if (!letrehoz) return NULL;
    ix->t[h].used = 1;
    ix->t[h].key = k;
    return &ix->t[h];
}

typedef struct { int off, frames, contig; } Egyseg;

/* a hang folyama a b vegere; az egysegek pozicioja a b-n beluli (abszolut), a cim = SONG_BASE + pozicio */
static void encode_voice(const All *T, int N, int loop, Buf *b, int *nref)
{
    Egyseg *units = xmalloc(sizeof(Egyseg) * (N + 1));
    int nu = 0;
    Index ix;
    double *lsize = xmalloc(sizeof(double) * (N + 1));
    All S = {0, 0, 128};
    int i = 0, prev_was_ref = 1, loop_off = -1, k, kezdet = b->n;
    uint8_t tmp[8];
    ix.meret = 1;
    while (ix.meret < N * 2 + 16) ix.meret <<= 1;
    ix.t = xmalloc(sizeof(Lista) * ix.meret);
    for (k = 0; k < N; k++) {
        if (k == 0 || !all_eq(T[k], T[k - 1])) lsize[k] = lit_bytes(k ? T[k - 1] : S, T[k], 0, tmp);
        else lsize[k] = 0.3;
    }
    while (i < N) {
        int limit = (loop < 0 || i >= loop) ? N - i : loop - i;
        int best_fr = 0, bj = 0, bcnt = 0;
        All bSS = S;
        if (i != 0 && i != loop) {
            Lista *L = index_get(&ix, T[i], 0);
            if (L) {
                int q, lo = L->n - 80 < 0 ? 0 : L->n - 80;
                for (q = L->n - 1; q >= lo; q--) {
                    int j = L->u[q], fr = 0, kk = j;
                    All SS = S;
                    while (kk < nu && kk - j < 255) {
                        Egyseg *e = &units[kk];
                        if (kk > j && !e->contig) break;
                        if (b->b[e->off] & 0x80) {
                            int qq, ok = 1;
                            if (fr + e->frames > limit) break;
                            for (qq = 0; qq < e->frames; qq++)
                                if (!all_eq(T[i + fr + qq], SS)) { ok = 0; break; }
                            if (!ok) break;
                            fr += e->frames;
                        } else {
                            int p = e->off;
                            All SS2 = apply_lit(SS, b->b, &p);
                            if (fr >= limit || !all_eq(T[i + fr], SS2)) break;
                            SS = SS2;
                            fr++;
                        }
                        kk++;
                    }
                    if (fr > best_fr) { best_fr = fr; bj = j; bcnt = kk - j; bSS = SS; }
                }
            }
        }
        if (best_fr) {
            double est = 0;
            for (k = i; k < i + best_fr; k++) est += lsize[k];
            if (est > 5) {
                int o = units[bj].off + SONG_BASE;
                bput(b, 0x10); bput(b, o & 0xFF); bput(b, o >> 8); bput(b, bcnt);
                S = bSS;
                i += best_fr;
                (*nref)++;
                prev_was_ref = 1;
                continue;
            }
        }
        {
            int off = b->n;
            Lista *L;
            if (i == loop) loop_off = off;
            if (all_eq(T[i], S) && i != 0 && i != loop) {
                int n = 1;
                while (n < 127 && i + n < N && all_eq(T[i + n], S) && (loop < 0 || i + n != loop)) n++;
                bput(b, 0x80 | n);
                units[nu].off = off; units[nu].frames = n; units[nu].contig = !prev_was_ref; nu++;
            } else {
                int n = lit_bytes(S, T[i], i == 0 || i == loop, tmp), q;
                for (q = 0; q < n; q++) bput(b, tmp[q]);
                S = T[i];
                units[nu].off = off; units[nu].frames = 1; units[nu].contig = !prev_was_ref; nu++;
            }
            L = index_get(&ix, T[i], 1);
            if (L->n == L->cap) { L->cap = L->cap ? L->cap * 2 : 4; L->u = xrealloc(L->u, sizeof(int) * L->cap); }
            L->u[L->n++] = nu - 1;
            i += units[nu - 1].frames;
            prev_was_ref = 0;
        }
    }
    {
        int o = (loop_off < 0 ? kezdet : loop_off) + SONG_BASE;
        bput(b, 0x11); bput(b, o & 0xFF); bput(b, o >> 8);
    }
    for (k = 0; k < ix.meret; k++) free(ix.t[k].u);
    free(ix.t);
    free(units);
    free(lsize);
}

/* a TVC dekodolo masa (ellenorzeshez): -> kepkockankenti allapot */
typedef struct { const uint8_t *m; int p, wait, refcnt, retp; All S; } Dek;

static All dek_frame(Dek *d)
{
    int c;
    if (d->wait) { d->wait--; return d->S; }
    for (;;) {
        c = d->m[d->p];
        if (c == 0x10) {
            d->retp = d->p + 4;
            d->refcnt = d->m[d->p + 3];
            d->p = d->m[d->p + 1] | (d->m[d->p + 2] << 8);
            continue;
        }
        if (c == 0x11) { d->p = d->m[d->p + 1] | (d->m[d->p + 2] << 8); continue; }
        break;
    }
    if (c & 0x80) { d->wait = (c & 0x7F) - 1; d->p++; }
    else d->S = apply_lit(d->S, d->m, &d->p);
    if (d->refcnt) { d->refcnt--; if (d->refcnt == 0) d->p = d->retp; }
    return d->S;
}

/* ================================================================== WAV elonezet (a TVC pontos hangja) */
static void tablak(uint8_t pages[17][256])
{
    int amp, i, shape;
    memset(pages, 0, 17 * 256);
    for (shape = 0; shape < 3; shape++)
        for (amp = 1; amp <= 5; amp++)
            for (i = 0; i < 256; i++) {
                int w = shape == 0 ? i >> 4 : shape == 1 ? ((i >> 3) < 16 ? (i >> 3) : 31 - (i >> 3)) : ZAJ[i];
                pages[1 + shape * 5 + amp - 1][i] = (uint8_t)(((w * amp + 7) / 15) * 4);
            }
    for (i = 0; i < 256; i++) pages[16][i] = (uint8_t)(((i >> 2) << 2) | 1);
}

static void w32(FILE *f, long v) { w16(f, (int)(v & 0xFFFF)); w16(f, (int)((v >> 16) & 0xFFFF)); }

static int wav_ir(const char *path, const All *T, int nfr)
{
    static uint8_t pages[17][256];
    const double FS = 3125000.0 / 16 / 39;
    const int OUT = 22050;
    long nport = (long)nfr * IT_PER_FRAME, nout, t;
    uint8_t *port = xmalloc(nport + 1);
    uint16_t ph[3] = {0, 0, 0};
    long pi = 0;
    int f, q, v;
    FILE *fo;
    tablak(pages);
    for (f = 0; f < nfr; f++)
        for (q = 0; q < IT_PER_FRAME; q++) {
            int tot = 0;
            for (v = 0; v < 3; v++) {
                All s = T[f * 3 + v];
                int hi;
                ph[v] = (uint16_t)(ph[v] + s.st);
                hi = ph[v] >> 8;
                if (s.sl & 0x80) tot += (hi < s.pw) ? (s.sl & 7) * 4 : 0;
                else tot += pages[s.sl][hi];
            }
            port[pi++] = (uint8_t)(pages[16][tot] >> 2);
        }
    nout = (long)(nport * OUT / FS);
    fo = fopen(path, "wb");
    if (!fo) { free(port); return 0; }
    fwrite("RIFF", 1, 4, fo); w32(fo, 36 + nout * 2); fwrite("WAVEfmt ", 1, 8, fo);
    w32(fo, 16); w16(fo, 1); w16(fo, 1); w32(fo, OUT); w32(fo, OUT * 2); w16(fo, 2); w16(fo, 16);
    fwrite("data", 1, 4, fo); w32(fo, nout * 2);
    for (t = 0; t < nout; t++) {
        long k = (long)(t * FS / OUT);
        int x = port[k < nport ? k : nport - 1];
        w16(fo, (int)((x - 7.5) / 7.5 * 20000));
    }
    fclose(fo);
    free(port);
    return 1;
}

/* ================================================================== 5. KISERLETI uj hang (csak WAV, -U): hangszinpaletta
   + okos hangero-elosztas. A .STC meg a regi; ez az A/B osszehasonlitashoz kell (a felhasznalo dont).
   - Hangszin: hangonkent, kepkockankent egy ciklus a SID valodi hullamabol (kevert hullamok = AND, gyurumodulacio
     es szinkron a forrashang periodusaval kozelitve), a TVC Nyquist-hataraig (2,5 kHz) savkorlatozva, a szurovel
     (6581-es vagofrekvencia-gorbe, LP/BP/HP, rezonancia) a felharmonikusokon. Ebbol 0..15-os, 256 byte-os tabla.
   - Paletta: dalonkent PAL_N tabla (sulyozott k-kozep a felharmonikus-spektrumon), + 1 zaj-tabla; kepkockankent
     a legkozelebbi. A tiszta, szuretlen negyszog marad a PW-osszehasonlitas (a TVC "res"-e).
   - Hangero: a tabla erteke (0..15) x szint (0..15) / 15 masodik tablaval. C = hangonkent legfeljebb 5 (mint most),
     D = a 15 szint elosztasa a szolo hangok kozott (elore nezve lassan valtozo erosites) + DC-kiegyenlites. */
#include <math.h>
#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif
#define UJ_M 1024                       /* egy ciklus mintai a spektrumhoz */
#define PAL_MAX 16
static int uj_wav = 0, uj_sec = 60, pal_n = 15;
static const double TVC_FS = 3125000.0 / 16 / 39;

typedef struct { uint8_t q[256]; double p; float ft[24]; double w; int pal; } Alak;
typedef struct { uint64_t key; int key2, idx; } AKulcs;
typedef struct { int tip, alak, step, pw; double a; } UjH;   /* tip: 0 csend, 1 tabla, 2 negyszog, 3 zaj */

static Alak *alakok; static int nalak, capalak;
static AKulcs *ahash; static int ahmeret;

static double fc6581(int r)
{
    static const int X[] = {0, 256, 384, 512, 640, 768, 896, 1023, 1024, 1280, 1536, 1792, 2047};
    static const double Y[] = {220, 250, 300, 420, 780, 1600, 3200, 6000, 4600, 7500, 10500, 13500, 18000};
    int i;
    for (i = 0; i < 12; i++)
        if (r <= X[i + 1]) return Y[i] + (Y[i + 1] - Y[i]) * (r - X[i]) / (double)(X[i + 1] - X[i] ? X[i + 1] - X[i] : 1);
    return 18000;
}

/* a szuro atvitele (abszolut ertek nelkul, komplex) f Hz-en */
static void szuro(double f, int fcr, int res, int mode, double *re, double *im)
{
    double fc = fc6581(fcr), x = f / fc, Q = 0.707 + 1.3 * res / 15.0;
    double dr = 1 - x * x, di = x / Q, d2 = dr * dr + di * di;
    double nr = 0, ni = 0;
    if (mode & 1) nr += 1;                       /* LP: 1 */
    if (mode & 2) ni += x;                       /* BP: jx */
    if (mode & 4) nr -= x * x;                   /* HP: -x^2 */
    *re = (nr * dr + ni * di) / d2;
    *im = (ni * dr - nr * di) / d2;
}

static void fft(double *re, double *im, int n)
{
    int i, j, k, m;
    for (i = 1, j = 0; i < n; i++) {
        int bit = n >> 1;
        for (; j & bit; bit >>= 1) j ^= bit;
        j ^= bit;
        if (i < j) { double t = re[i]; re[i] = re[j]; re[j] = t; t = im[i]; im[i] = im[j]; im[j] = t; }
    }
    for (m = 2; m <= n; m <<= 1) {
        double a = -2 * M_PI / m;
        for (k = 0; k < n; k += m)
            for (j = 0; j < m / 2; j++) {
                double wr = cos(a * j), wi = sin(a * j);
                double xr = re[k + j + m / 2] * wr - im[k + j + m / 2] * wi;
                double xi = re[k + j + m / 2] * wi + im[k + j + m / 2] * wr;
                re[k + j + m / 2] = re[k + j] - xr; im[k + j + m / 2] = im[k + j] - xi;
                re[k + j] += xr; im[k + j] += xi;
            }
    }
}

static void alak_jegy(Alak *a)                /* a 0..15-os tabla felharmonikus-spektruma (egysegnyi hossz) */
{
    double re[256], im[256], s = 0;
    int i;
    for (i = 0; i < 256; i++) { re[i] = a->q[i]; im[i] = 0; }
    fft(re, im, 256);
    for (i = 0; i < 24; i++) { a->ft[i] = (float)sqrt(sqrt(re[i + 1] * re[i + 1] + im[i + 1] * im[i + 1])); s += a->ft[i] * a->ft[i]; }
    s = sqrt(s);
    for (i = 0; i < 24; i++) a->ft[i] = (float)(s > 0 ? a->ft[i] / s : 0);
}

/* egy ciklus: hullam (ctrl felso 4 bit), sajat F, forras Fs (gyuru/szinkron), pw (12 bit), szuro (route=1 eseten) */
static int alak_keres(int wave, int ring, int sync, int F, int Fs, int fb, int pw, int route, int fcr, int res, int mode)
{
    uint64_t key = (uint64_t)wave | ((uint64_t)ring << 4) | ((uint64_t)sync << 5) | ((uint64_t)route << 6)
                 | ((uint64_t)F << 7) | ((uint64_t)((ring || sync) ? Fs : 0) << 23) | ((uint64_t)((wave & 4) ? pw : 0) << 39)
                 | ((uint64_t)(route ? fcr : 0) << 51);
    int key2 = route ? (res | (mode << 4)) : 0;
    unsigned h = (unsigned)(((key ^ ((uint64_t)key2 << 57)) * 0x9E3779B97F4A7C15ULL) >> 40);
    static double re[UJ_M], im[UJ_M];
    double s[256], mn = 1e9, mx = -1e9, fbhz, fmax;
    int i, k, K, idx;
    Alak *a;
    if (!ahash) { ahmeret = 1 << 18; ahash = xmalloc(sizeof(AKulcs) * ahmeret); for (i = 0; i < ahmeret; i++) ahash[i].idx = -1; }
    idx = h & (ahmeret - 1);
    while (ahash[idx].idx >= 0) { if (ahash[idx].key == key && ahash[idx].key2 == key2) return ahash[idx].idx; idx = (idx + 1) & (ahmeret - 1); }
    if (nalak * 2 > ahmeret) { fprintf(stderr, "tul sok hangszin\n"); exit(2); }
    for (i = 0; i < UJ_M; i++) {
        uint32_t acc = (uint32_t)fmod((double)i / UJ_M * F / fb * 16777216.0, 16777216.0);
        uint32_t sacc = (uint32_t)fmod((double)i / UJ_M * Fs / fb * 16777216.0, 16777216.0);
        int msb = (acc >> 23) & 1, o = 0xFFF;
        if (ring) msb ^= (sacc >> 23) & 1;
        if (wave & 1) o &= (int)(((msb ? ~acc : acc) >> 11) & 0xFFF);
        if (wave & 2) o &= (int)(acc >> 12);
        if (wave & 4) o &= ((int)(acc >> 12) >= pw) ? 0xFFF : 0;
        re[i] = o / 4095.0 * 2 - 1; im[i] = 0;
    }
    fft(re, im, UJ_M);
    fbhz = fb * PAL_CLK / 16777216.0;
    fmax = TVC_FS * 0.5;
    K = (int)(fmax / (fbhz > 1 ? fbhz : 1));
    if (K > 120) K = 120;
    for (i = 0; i < 256; i++) s[i] = 0;
    for (k = 1; k <= K; k++) {
        double cr = re[k] / (UJ_M / 2), ci = im[k] / (UJ_M / 2);
        if (route) {
            double hr, hi, t;
            szuro(k * fbhz, fcr, res, mode, &hr, &hi);
            t = cr * hr - ci * hi; ci = cr * hi + ci * hr; cr = t;
        }
        for (i = 0; i < 256; i++) {
            double ph = 2 * M_PI * k * i / 256.0;
            s[i] += cr * cos(ph) - ci * sin(ph);
        }
    }
    for (i = 0; i < 256; i++) { if (s[i] < mn) mn = s[i]; if (s[i] > mx) mx = s[i]; }
    if (nalak == capalak) { capalak = capalak ? capalak * 2 : 1024; alakok = xrealloc(alakok, sizeof(Alak) * capalak); }
    a = &alakok[nalak];
    memset(a, 0, sizeof(Alak));
    a->p = (mx - mn) / 2;
    for (i = 0; i < 256; i++) a->q[i] = (uint8_t)(a->p > 1e-6 ? (int)((s[i] - mn) / (mx - mn) * 15 + 0.5) : 7);
    alak_jegy(a);
    ahash[idx].key = key; ahash[idx].key2 = key2; ahash[idx].idx = nalak;
    return nalak++;
}

static double jdist(const float *a, const float *b)
{
    double d = 0; int i;
    for (i = 0; i < 24; i++) { double t = a[i] - b[i]; d += t * t; }
    return d;
}

/* sulyozott k-kozep -> pal[k] = a kozephez legkozelebbi alak (valodi tabla) */
static int paletta(int *pal)
{
    float C[PAL_MAX][24];
    double W[PAL_MAX], acc[PAL_MAX][24];
    int n = 0, i, k, it, j;
    uint32_t r = 12345;
    double best;
    for (i = 0; i < nalak; i++) if (alakok[i].w > 0) n++;
    if (n == 0) return 0;
    /* k-means++ (determinisztikus): az elso a legnagyobb sulyu, utana a legtavolabbi (sullyal) */
    best = -1; k = 0;
    for (i = 0; i < nalak; i++) if (alakok[i].w > best) { best = alakok[i].w; k = i; }
    memcpy(C[0], alakok[k].ft, sizeof(C[0]));
    for (j = 1; j < pal_n; j++) {
        double bd = -1; int bi = -1;
        for (i = 0; i < nalak; i++) {
            double d = 1e9; int c;
            if (alakok[i].w <= 0) continue;
            for (c = 0; c < j; c++) { double t = jdist(alakok[i].ft, C[c]); if (t < d) d = t; }
            d *= alakok[i].w;
            if (d > bd) { bd = d; bi = i; }
        }
        if (bi < 0 || bd <= 0) break;
        memcpy(C[j], alakok[bi].ft, sizeof(C[0]));
    }
    k = j;
    (void)r;
    for (it = 0; it < 40; it++) {
        memset(W, 0, sizeof(W)); memset(acc, 0, sizeof(acc));
        for (i = 0; i < nalak; i++) {
            double d = 1e9; int c, bc = 0;
            if (alakok[i].w <= 0) continue;
            for (c = 0; c < k; c++) { double t = jdist(alakok[i].ft, C[c]); if (t < d) { d = t; bc = c; } }
            alakok[i].pal = bc;
            W[bc] += alakok[i].w;
            for (j = 0; j < 24; j++) acc[bc][j] += alakok[i].w * alakok[i].ft[j];
        }
        for (i = 0; i < k; i++) if (W[i] > 0) for (j = 0; j < 24; j++) C[i][j] = (float)(acc[i][j] / W[i]);
    }
    for (i = 0; i < k; i++) {
        double d = 1e9; int bi = -1, a;
        for (a = 0; a < nalak; a++) {
            double t;
            if (alakok[a].w <= 0 || alakok[a].pal != i) continue;
            t = jdist(alakok[a].ft, C[i]);
            if (t < d) { d = t; bi = a; }
        }
        pal[i] = bi;
    }
    /* minden alak (a nem hasznaltak is) a legkozelebbi paletta-tablat kapja */
    for (i = 0; i < nalak; i++) {
        double d = 1e9; int c, bc = 0;
        for (c = 0; c < k; c++) { double t; if (pal[c] < 0) continue; t = jdist(alakok[i].ft, alakok[pal[c]].ft); if (t < d) { d = t; bc = c; } }
        alakok[i].pal = bc;
    }
    return k;
}

static void wav_fej(FILE *fo, long nout, int rate)
{
    fwrite("RIFF", 1, 4, fo); w32(fo, 36 + nout * 2); fwrite("WAVEfmt ", 1, 8, fo);
    w32(fo, 16); w16(fo, 1); w16(fo, 1); w32(fo, rate); w32(fo, rate * 2); w16(fo, 2); w16(fo, 16);
    fwrite("data", 1, 4, fo); w32(fo, nout * 2);
}

/* port-ertekek (0..15, TVC_FS) -> WAV 22050 Hz (tartott minta, mint a TVC DAC-ja) */
static int port_wav(const char *path, const uint8_t *port, long nport)
{
    const int OUT = 22050;
    long nout = (long)(nport * OUT / TVC_FS), t;
    FILE *fo = fopen(path, "wb");
    if (!fo) return 0;
    wav_fej(fo, nout, OUT);
    for (t = 0; t < nout; t++) {
        long k = (long)(t * TVC_FS / OUT);
        w16(fo, (int)((port[k < nport ? k : nport - 1] - 7.5) / 7.5 * 20000));
    }
    fclose(fo);
    return 1;
}

/* a kepkocka indexe hurokkal kiterjesztve */
static int kk(int f, int n, int loop) { return f < n ? f : (loop >= 0 ? loop + (f - n) % (n - loop) : f % n); }

static void uj_hang(const Dump *dp, const All *T, const char *mappa, int song, int mem_n, int mem_loop)
{
    uint8_t regs[32];
    Env env[3];
    int n = dp->n, nf = uj_sec * 50, f, v, i, q, npal, pal[PAL_MAX];
    UjH *H = xmalloc(sizeof(UjH) * 3 * nf);
    uint8_t (*lvl)[3] = xmalloc(3 * (size_t)nf);
    uint8_t *ofs = xmalloc(nf);
    uint8_t *port = xmalloc((size_t)nf * IT_PER_FRAME);
    double *G = xmalloc(sizeof(double) * nf);
    char fajl[1200];
    int var;
    nalak = 0;
    if (ahash) for (i = 0; i < ahmeret; i++) ahash[i].idx = -1;
    memset(regs, 0, sizeof(regs));
    memset(env, 0, sizeof(env));
    for (v = 0; v < 3; v++) env[v].state = 2;
    /* 1. kepkockankent a hangok (a tvc_allapotok logikaja, de a teljes SID-allapotbol). A memoria-hurok szerint
          ismetlunk, a burkolo folyamatosan fut (a hang-hurok a regi, durva allapotbol szamol: lecsengo hangot
          "kitartottnak" lathat). */
    for (f = 0; f < nf; f++) {
        int mid[3], vol, fcr, res, route, mode, sf = kk(f, mem_n, mem_loop);
        for (i = 0; i < dp->k[sf].n; i++) {
            int r = dp->k[sf].w[i].r, val = dp->k[sf].w[i].v;
            regs[r] = (uint8_t)val;
            if (r < 21) {
                Env *e = &env[r / 7];
                if (r % 7 == 4) env_control(e, val);
                else if (r % 7 == 5) { e->a = val >> 4; e->d = val & 15; }
                else if (r % 7 == 6) { e->s = val >> 4; e->r = val & 15; }
            }
        }
        for (v = 0; v < 3; v++) {
            env_run(&env[v], FRAME_CYC / 2);
            mid[v] = env[v].lvl;
            env_run(&env[v], FRAME_CYC - FRAME_CYC / 2);
        }
        vol = regs[24] & 15;
        fcr = (regs[21] & 7) | (regs[22] << 3);
        res = regs[23] >> 4; route = regs[23] & 7; mode = (regs[24] >> 4) & 7;
        for (v = 0; v < 3; v++) {
            int b = v * 7, src = (v + 2) % 3;
            int F = regs[b] | (regs[b + 1] << 8), Fs = regs[src * 7] | (regs[src * 7 + 1] << 8);
            int ctrl = regs[b + 4], wave = ctrl >> 4;
            int pw = regs[b + 2] | ((regs[b + 3] & 15) << 8);
            int ring = (ctrl & 4) && (wave & 1) && Fs > 0, sync = (ctrl & 2) && Fs > 0;
            int rt = (route >> v) & 1, fb;
            UjH *u = &H[f * 3 + v];
            double a = mid[v] / 255.0 * vol / 15.0;
            memset(u, 0, sizeof(UjH));
            if ((ctrl & 8) || wave == 0 || F == 0 || a <= 0) continue;
            if (v == 2 && (regs[24] & 0x80) && !rt) continue;      /* 3. hang ki */
            if (rt && mode == 0) continue;
            if (wave & 8) {                                        /* zaj: a fix zaj-tabla */
                double s = 0; int j;
                if (rt) {
                    for (j = 1; j <= 24; j++) { double hr, hi; szuro(j * 100.0, fcr, res, mode, &hr, &hi); s += sqrt(hr * hr + hi * hi); }
                    s /= 24; if (s > 1) s = 1;
                } else s = 1;
                u->tip = 3; u->a = a * s;
                u->step = (int)(F * STEP_MUL + 0.5) / 16; if (u->step < 1) u->step = 1;
                continue;
            }
            if (wave == 4 && !rt && !sync) {                       /* tiszta negyszog: PW-osszehasonlitas */
                u->tip = 2; u->a = a; u->pw = pw >> 4;
                u->step = (int)(F * STEP_MUL + 0.5);
                continue;
            }
            fb = (sync || ring) ? (sync ? Fs : (Fs < F ? Fs : F)) : F;
            u->tip = 1;
            u->alak = alak_keres(wave & 7, ring, sync, F, Fs, fb, pw, rt, fcr, res, mode);
            u->a = a * alakok[u->alak].p;
            u->step = (int)(fb * STEP_MUL + 0.5);
            alakok[u->alak].w += u->a;
        }
    }
    for (i = 0; i < 3 * nf; i++) if (H[i].step > 0xFFFF) H[i].step = 0xFFFF;
    /* 2. paletta */
    npal = paletta(pal);
    info("  uj hang: %d kulonbozo hangszin -> %d tablas paletta + zaj (%d byte)\n", nalak, npal, (npal + 1) * 256);
    /* 3. hangero: C = mint most (hangonkent max 5), D = okos elosztas */
    for (var = 0; var < 2; var++) {
        uint16_t ph[3] = {0, 0, 0};
        long pi = 0;
        if (var == 1) {
            /* a kepkocka kivant erositese: egy teljes hang = 15 szint; elore nezve lassan le, lassan fel */
            const double LE = 0.06, FEL = 0.025;    /* log2 egyseg / kepkocka */
            for (f = 0; f < nf; f++) {
                double s = 0;
                for (v = 0; v < 3; v++) s += H[f * 3 + v].a;
                G[f] = s > 1 ? log2(1 / s) : 0;
            }
            for (f = nf - 2; f >= 0; f--) if (G[f] > G[f + 1] + LE) G[f] = G[f + 1] + LE;
            for (f = 1; f < nf; f++) if (G[f] > G[f - 1] + FEL) G[f] = G[f - 1] + FEL;
        }
        for (f = 0; f < nf; f++) {
            const UjH *u = &H[f * 3];
            int L[3], sum = 0;
            if (var == 0) {
                for (v = 0; v < 3; v++) { int l = (int)(u[v].a * 5 + 0.5); L[v] = u[v].tip ? (l > 5 ? 5 : l) : 0; sum += L[v]; }
                ofs[f] = 0;
            } else {
                double g = pow(2, G[f]) * 15, fr[3];
                for (v = 0; v < 3; v++) { double x = u[v].tip ? u[v].a * g : 0; L[v] = (int)x; fr[v] = x - L[v]; sum += L[v]; }
                while (sum > 15) { int m = 0; for (v = 1; v < 3; v++) if (L[v] > L[m]) m = v; L[m]--; sum--; }
                for (;;) {           /* maradek: a legnagyobb tortresz kap, amig belefer */
                    int m = -1; double bf = 0.5;
                    for (v = 0; v < 3; v++) if (fr[v] >= bf) { bf = fr[v]; m = v; }
                    if (m < 0 || sum >= 15) break;
                    L[m]++; fr[m] = 0; sum++;
                }
                ofs[f] = (uint8_t)((15 - sum) / 2);
            }
            for (v = 0; v < 3; v++) lvl[f][v] = (uint8_t)L[v];
            for (q = 0; q < IT_PER_FRAME; q++) {
                int tot = ofs[f];
                for (v = 0; v < 3; v++) {
                    int hi, x;
                    ph[v] = (uint16_t)(ph[v] + u[v].step);
                    hi = ph[v] >> 8;
                    switch (u[v].tip) {
                    case 1: x = alakok[pal[alakok[u[v].alak].pal]].q[hi]; break;
                    case 2: x = hi < u[v].pw ? 15 : 0; break;
                    case 3: x = ZAJ[hi]; break;
                    default: x = 0;
                    }
                    tot += (x * L[v] + 7) / 15;
                }
                port[pi++] = (uint8_t)(tot > 15 ? 15 : tot);
            }
        }
        snprintf(fajl, sizeof(fajl), "%s/SONG%d_%s.WAV", mappa, song, var ? "D_hangero" : "C_paletta");
        if (port_wav(fajl, port, pi)) info("  WAV: %s\n", fajl);
    }
    /* B = a mostani TVC-hang ugyanilyen hosszan */
    {
        All *E = xmalloc(sizeof(All) * 3 * nf);
        for (f = 0; f < nf; f++) memcpy(&E[f * 3], &T[kk(f, n, dp->loop) * 3], sizeof(All) * 3);
        snprintf(fajl, sizeof(fajl), "%s/SONG%d_B_most.WAV", mappa, song);
        if (wav_ir(fajl, E, nf)) info("  WAV: %s\n", fajl);
        free(E);
    }
    free(H); free(lvl); free(ofs); free(port); free(G);
}

/* ================================================================== egy aldal */
static const char *nev_kapcsolo = NULL;     /* -n NEV */
static int csak_mem = 0;                    /* -m: csak a memoria-hurok (a regi viselkedes) */

static void tvc_nev(const char *path, char *nev)
{
    const char *b = path, *p;
    int n = 0;
    if (nev_kapcsolo) b = nev_kapcsolo;
    else for (p = path; *p; p++) if (*p == '/' || *p == '\\') b = p + 1;
    for (p = b; *p && *p != '.' && n < 8; p++) {
        int ch = toupper((unsigned char)*p);
        if (isalnum(ch) || ch == '_' || ch == '-') nev[n++] = (char)ch;
    }
    if (n == 0) { strcpy(nev, "SID"); return; }
    nev[n] = 0;
}

static void mkdir_p(const char *path)
{
    char tmp[1024];
    size_t i;
    snprintf(tmp, sizeof(tmp), "%s", path);
    for (i = 1; tmp[i]; i++)
        if (tmp[i] == '/' || tmp[i] == '\\') { char c = tmp[i]; tmp[i] = 0; MKDIR(tmp); tmp[i] = c; }
    MKDIR(tmp);
}

static int aldal(const SidFajl *s, const char *path, int song, const char *outdir, int maxf, int wav)
{
    Dump dp;
    All *T, *Tv;
    Buf blob = {0};
    int v, k, nref = 0, starts[3], f, mem_n, mem_loop, hang = 0;
    char hiba[256] = "", nev[16], mappa[1024], fajl[1100];
    FILE *fo;
    if (!dump(s, song, csak_mem ? maxf : 2 * maxf, &dp, hiba)) {
        fprintf(stderr, "%s, %d. aldal: %s\n", path, song, hiba);
        return 0;
    }
    T = tvc_allapotok(&dp);
    mem_n = dp.n; mem_loop = dp.loop;
    if (!csak_mem) hang = hang_hurok(T, &dp.n, &dp.loop);
    if (dp.loop < 0 && dp.n > maxf) dp.n = maxf;      /* hurok nelkul legfeljebb maxf kepkocka (aztan elolrol) */
    Tv = xmalloc(sizeof(All) * (dp.n + 1));
    for (;;) {
        blob.n = 0; nref = 0;
        for (k = 0; k < 6; k++) bput(&blob, 0);
        for (v = 0; v < 3; v++) {
            for (f = 0; f < dp.n; f++) Tv[f] = T[f * 3 + v];
            starts[v] = blob.n;
            encode_voice(Tv, dp.n, dp.loop, &blob, &nref);
        }
        /* a 10 perc utani hurok nem fer el -> inkabb a regi mod: maxf kepkocka, aztan elolrol */
        if (blob.n > SONG_MAX && dp.n > maxf) { dp.n = maxf; dp.loop = -1; hang = 0; mem_loop = -2; continue; }
        break;
    }
    for (v = 0; v < 3; v++) {
        int a = SONG_BASE + starts[v];
        blob.b[2 * v] = (uint8_t)(a & 0xFF);
        blob.b[2 * v + 1] = (uint8_t)(a >> 8);
    }
    if (debug_ki) {
        FILE *fd = fopen(debug_ki, "wb");
        if (fd) {
            for (f = 0; f < dp.n * 3; f++) { w16(fd, T[f].st); fputc(T[f].sl, fd); fputc(T[f].pw, fd); }
            fwrite(blob.b, 1, blob.n, fd);
            fclose(fd);
        }
    }
    tvc_nev(path, nev);
    snprintf(mappa, sizeof(mappa), "%s/%s", outdir, nev);
    mkdir_p(mappa);
    info("%s / %s - %d. aldal: %d kepkocka (%d:%02d), hurok: ", s->name, s->author, song, dp.n,
         dp.n / 50 / 60, dp.n / 50 % 60);
    if (dp.loop >= 0) {
        int P = dp.n - dp.loop;
        if (P == 1) info("%d:%02d-tol csend/kitartott hang (vege)", dp.loop / 50 / 60, dp.loop / 50 % 60);
        else info("%d:%02d-tol, %d:%02d hosszu", dp.loop / 50 / 60, dp.loop / 50 % 60, P / 50 / 60, P / 50 % 60);
        info(hang ? " [hang]" : " [memoria]");
    } else info(mem_loop == -2 ? "van 10 perc utan, de ugy nem fer el -> 10 perc, aztan elolrol" : "nincs (elolrol)");
    if (hang) {
        if (mem_loop >= 0) info(" (memoria szerint: %d:%02d-tol, %d:%02d)", mem_loop / 50 / 60, mem_loop / 50 % 60,
                                (mem_n - mem_loop) / 50 / 60, (mem_n - mem_loop) / 50 % 60);
        else info(" (memoria szerint: nincs)");
    }
    info(", %d byte (%d REF)", blob.n, nref);
    if (blob.n > SONG_MAX) {
        info("\n");
        fprintf(stderr, "  TUL NAGY: %d byte, a TVC-n legfeljebb %d fer el - nem irtam ki\n", blob.n, SONG_MAX);
        return 0;
    }
    /* ellenorzes: a TVC dekodoloja pontosan ezt adja vissza (+ 200 kepkocka a hurok utan) */
    {
        uint8_t *m = xmalloc(65536);
        Dek d[3];
        int extra = 200;
        memcpy(m + SONG_BASE, blob.b, blob.n);
        for (v = 0; v < 3; v++) {
            memset(&d[v], 0, sizeof(Dek));
            d[v].m = m;
            d[v].p = blob.b[2 * v] | (blob.b[2 * v + 1] << 8);
            d[v].S.pw = 128;
        }
        for (f = 0; f < dp.n + extra; f++)
            for (v = 0; v < 3; v++) {
                All a = dek_frame(&d[v]);
                int ref = f < dp.n ? f : (dp.loop >= 0 ? dp.loop : 0) + (f - dp.n);
                if (ref < dp.n && !all_eq(a, T[ref * 3 + v])) {
                    fprintf(stderr, "BELSO HIBA: a dekodolo elter (%d. kepkocka, %d. hang)\n", f, v);
                    return 0;
                }
            }
        free(m);
    }
    snprintf(fajl, sizeof(fajl), "%s/SONG%d.STC", mappa, song);
    fo = fopen(fajl, "wb");
    if (!fo) { fprintf(stderr, "\nnem irhato: %s\n", fajl); return 0; }
    {
        int split = 0xC000 - SONG_BASE;
        w16(fo, 0xFFFF);                        /* 1.1: info-blokk */
        info_ir(fo, s->name);
        info_ir(fo, s->author);
        info_ir(fo, s->released);
        w16(fo, blob.n);
        if (blob.n > split) fwrite(blob.b + split, 1, blob.n - split, fo);
        fwrite(blob.b, 1, blob.n < split ? blob.n : split, fo);
    }
    fclose(fo);
    info(" -> %s\n", fajl);
    if (wav) {
        snprintf(fajl, sizeof(fajl), "%s/SONG%d.WAV", mappa, song);
        if (wav_ir(fajl, T, dp.n)) info("  WAV: %s\n", fajl);
    }
    if (uj_wav) uj_hang(&dp, T, mappa, song, mem_n, mem_loop < 0 ? -1 : mem_loop);
    for (f = 0; f < mem_n; f++) free(dp.k[f].w);
    free(dp.k);
    free(T);
    free(Tv);
    free(blob.b);
    return 1;
}

static void hasznalat(void)
{
    printf("sid2tvc " VERZIO " - C64 .sid -> TVC SIDSoftEMU dal (.STC)\n"
           "hasznalat: sid2tvc [-s N | -a] [-o MAPPA] [-n NEV] [-w] [-f N] [-m] [-q] fajl.sid\n"
           "  -s N      aldal (alapertelmezes: a .sid kezdo dala)\n"
           "  -a        az osszes aldal\n"
           "  -o MAPPA  kimenet: MAPPA/<NEV>/SONG<n>.STC (alapertelmezes: SID_TVC)\n"
           "  -n NEV    a mappa neve (legfeljebb 8 betu; alapertelmezes: a .sid fajlnevebol)\n"
           "  -w        WAV elonezet is (a TVC hangja): MAPPA/<NEV>/SONG<n>.WAV\n"
           "  -f N      hurok nelkul legfeljebb N kepkocka (50/mp, alapertelmezes 30000 = 10 perc)\n"
           "  -m        csak a memoria-hurok (a hang ismetlodeset nem keresi)\n"
           "  -q        csak a hibak\n");
}

int main(int argc, char **argv)
{
    const char *path = NULL, *outdir = "SID_TVC";
    int song = 0, osszes = 0, wav = 0, maxf = 30000, i, jo = 1;
    SidFajl s;
    STEP_MUL = PAL_CLK * 65536 / (16777216 * (3125000.0 / 16 / 39));
    for (i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "-s") && i + 1 < argc) song = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-a")) osszes = 1;
        else if (!strcmp(argv[i], "-o") && i + 1 < argc) outdir = argv[++i];
        else if (!strcmp(argv[i], "-n") && i + 1 < argc) nev_kapcsolo = argv[++i];
        else if (!strcmp(argv[i], "-w")) wav = 1;
        else if (!strcmp(argv[i], "-m")) csak_mem = 1;
        else if (!strcmp(argv[i], "-U")) uj_wav = 1;
        else if (!strcmp(argv[i], "-t") && i + 1 < argc) uj_sec = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-P") && i + 1 < argc) { pal_n = atoi(argv[++i]); if (pal_n < 1) pal_n = 1; if (pal_n > PAL_MAX) pal_n = PAL_MAX; }
        else if (!strcmp(argv[i], "-f") && i + 1 < argc) maxf = atoi(argv[++i]);
        else if (!strcmp(argv[i], "-q")) csendes = 1;
        else if (!strcmp(argv[i], "-D") && i + 1 < argc) debug_ki = argv[++i];
        else if (argv[i][0] == '-') { hasznalat(); return 1; }
        else path = argv[i];
    }
    if (!path) { hasznalat(); return 1; }
    if (!sid_olvas(path, &s)) return 1;
    if (maxf < 1) maxf = 1;
    info("%s: %s, %d aldal (kezdo: %d), load $%04X init $%04X play $%04X\n", path, s.magic, s.songs, s.start,
         s.load, s.init, s.play);
    if (osszes) {
        for (i = 1; i <= s.songs; i++) if (!aldal(&s, path, i, outdir, maxf, wav)) jo = 0;
    } else {
        if (song == 0) song = s.start ? s.start : 1;
        if (song < 1 || song > s.songs) { fprintf(stderr, "nincs ilyen aldal: %d (1..%d)\n", song, s.songs); return 1; }
        jo = aldal(&s, path, song, outdir, maxf, wav);
    }
    return jo ? 0 : 1;
}
