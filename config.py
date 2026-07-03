from pathlib import Path

# Ticker List
TICKERS = ["AADI.JK", "AALI.JK", "ABBA.JK", "ABDA.JK", "ABMM.JK", "ACES.JK", "ACRO.JK", "ACST.JK", 
           "ADCP.JK", "ADES.JK", "ADHI.JK", "ADMF.JK", "ADMG.JK", "ADMR.JK", "ADRO.JK", "AEGS.JK", 
           "AGAR.JK", "AGII.JK", "AGRO.JK", "AGRS.JK", "AHAP.JK", "AIMS.JK", "AISA.JK", "AKKU.JK", 
           "AKPI.JK", "AKRA.JK", "AKSI.JK", "ALDO.JK", "ALII.JK", "ALKA.JK", "ALMI.JK", "ALTO.JK", 
           "AMAG.JK", "AMAN.JK", "AMAR.JK", "AMFG.JK", "AMIN.JK", "AMMN.JK", "AMMS.JK", "AMOR.JK", 
           "AMRT.JK", "ANDI.JK", "ANJT.JK", "ANTM.JK", "APEX.JK", "APIC.JK", "APII.JK", "APLI.JK", 
           "APLN.JK", "ARCI.JK", "AREA.JK", "ARGO.JK", "ARII.JK", "ARKA.JK", "ARKO.JK", "ARNA.JK", 
           "ARTA.JK", "ARTO.JK", "ASBI.JK", "ASDM.JK", "ASGR.JK", "ASHA.JK", "ASII.JK", "ASJT.JK", 
           "ASLC.JK", "ASLI.JK", "ASMI.JK", "ASPI.JK", "ASPR.JK", "ASRI.JK", "ASRM.JK", "ASSA.JK", 
           "ATAP.JK", "ATIC.JK", "ATLA.JK", "AUTO.JK", "AVIA.JK", "AWAN.JK", "AXIO.JK", "AYAM.JK", 
           "AYLS.JK", "BABP.JK", "BABY.JK", "BACA.JK", "BAIK.JK", "BAJA.JK", "BALI.JK", "BANK.JK", 
           "BAPA.JK", "BAPI.JK", "BATA.JK", "BATR.JK", "BAUT.JK", "BAYU.JK", "BBCA.JK", "BBHI.JK", 
           "BBKP.JK", "BBLD.JK", "BBMD.JK", "BBNI.JK", "BBRI.JK", "BBRM.JK", "BBSI.JK", "BBSS.JK", 
           "BBTN.JK", "BBYB.JK", "BCAP.JK", "BCIC.JK", "BCIP.JK", "BDKR.JK", "BDMN.JK", "BEBS.JK", 
           "BEEF.JK", "BEER.JK", "BEKS.JK", "BELI.JK", "BELL.JK", "BESS.JK", "BEST.JK", "BFIN.JK", 
           "BGTG.JK", "BHAT.JK", "BHIT.JK", "BIKE.JK", "BIMA.JK", "BINA.JK", "BINO.JK", "BIPI.JK", 
           "BIPP.JK", "BIRD.JK", "BISI.JK", "BJBR.JK", "BJTM.JK", "BKDP.JK", "BKSL.JK", "BKSW.JK", 
           "BLES.JK", "BLOG.JK", "BLTA.JK", "BLTZ.JK", "BLUE.JK", "BMAS.JK", "BMBL.JK", "BMHS.JK", 
           "BMRI.JK", "BMSR.JK", "BMTR.JK", "BNBA.JK", "BNBR.JK", "BNGA.JK", "BNII.JK", "BNLI.JK", 
           "BOAT.JK", "BOBA.JK", "BOGA.JK", "BOLA.JK", "BOLT.JK", "BPFI.JK", "BPII.JK", "BPTR.JK", 
           "BRAM.JK", "BREN.JK", "BRIS.JK", "BRMS.JK", "BRNA.JK", "BRPT.JK", "BRRC.JK", "BSBK.JK", 
           "BSDE.JK", "BSIM.JK", "BSML.JK", "BSSR.JK", "BSWD.JK", "BTEK.JK", "BTON.JK", "BTPN.JK", 
           "BTPS.JK", "BUAH.JK", "BUDI.JK", "BUKA.JK", "BUKK.JK", "BULL.JK", "BUMI.JK", "BUVA.JK", 
           "BVIC.JK", "BWPT.JK", "BYAN.JK", "CAKK.JK", "CAMP.JK", "CANI.JK", "CARE.JK", "CARS.JK", 
           "CASA.JK", "CASH.JK", "CASS.JK", "CBDK.JK", "CBPE.JK", "CBRE.JK", "CBUT.JK", "CCSI.JK", 
           "CDIA.JK", "CEKA.JK", "CENT.JK", "CFIN.JK", "CGAS.JK", "CHEK.JK", "CHEM.JK", "CHIP.JK", 
           "CINT.JK", "CITA.JK", "CITY.JK", "CLAY.JK", "CLEO.JK", "CLPI.JK", "CMNP.JK", "CMNT.JK", 
           "CMPP.JK", "CMRY.JK", "CNKO.JK", "CNMA.JK", "COAL.JK", "COCO.JK", "COIN.JK", "CPIN.JK", 
           "CPRO.JK", "CRAB.JK", "CRSN.JK", "CSAP.JK", "CSIS.JK", "CSMI.JK", "CSRA.JK", "CTBN.JK", 
           "CTRA.JK", "CTTH.JK", "CUAN.JK", "CYBR.JK", "DAAZ.JK", "DADA.JK", "DART.JK", "DATA.JK", 
           "DAYA.JK", "DCII.JK", "DEFI.JK", "DEPO.JK", "DEWA.JK", "DEWI.JK", "DFAM.JK", "DGIK.JK", 
           "DGNS.JK", "DGWG.JK", "DIGI.JK", "DILD.JK", "DIVA.JK", "DKFT.JK", "DKHH.JK", "DLTA.JK", 
           "DMAS.JK", "DMMX.JK", "DMND.JK", "DNAR.JK", "DNET.JK", "DOID.JK", "DOOH.JK", "DOSS.JK", 
           "DPNS.JK", "DPUM.JK", "DRMA.JK", "DSFI.JK", "DSNG.JK", "DSSA.JK", "DUTI.JK", "DVLA.JK", 
           "DWGL.JK", "DYAN.JK", "EAST.JK", "ECII.JK", "EDGE.JK", "EKAD.JK", "ELIT.JK", "ELPI.JK", 
           "ELSA.JK", "ELTY.JK", "EMAS.JK", "EMDE.JK", "EMTK.JK", "ENAK.JK", "ENRG.JK", "ENZO.JK", 
           "EPAC.JK", "EPMT.JK", "ERAA.JK", "ERAL.JK", "ERTX.JK", "ESIP.JK", "ESSA.JK", "ESTA.JK", 
           "ESTI.JK", "EURO.JK", "EXCL.JK", "FAPA.JK", "FAST.JK", "FASW.JK", "FILM.JK", "FIMP.JK", 
           "FIRE.JK", "FISH.JK", "FITT.JK", "FLMC.JK", "FMII.JK", "FOLK.JK", "FOOD.JK", "FORE.JK", 
           "FORU.JK", "FPNI.JK", "FUJI.JK", "FUTR.JK", "FWCT.JK", "GDST.JK", "GDYR.JK", "GEMA.JK", 
           "GEMS.JK", "GGRM.JK", "GGRP.JK", "GHON.JK", "GIAA.JK", "GJTL.JK", "GLOB.JK", "GLVA.JK", 
           "GMFI.JK", "GMTD.JK", "GOLD.JK", "GOLF.JK", "GOOD.JK", "GOTO.JK", "GPRA.JK", "GPSO.JK", 
           "GRIA.JK", "GRPH.JK", "GRPM.JK", "GSMF.JK", "GTBO.JK", "GTRA.JK", "GTSI.JK", "GULA.JK", 
           "GUNA.JK", "GWSA.JK", "GZCO.JK", "HADE.JK", "HAIS.JK", "HAJJ.JK", "HALO.JK", "HATM.JK", 
           "HBAT.JK", "HDFA.JK", "HDIT.JK", "HEAL.JK", "HELI.JK", "HERO.JK", "HEXA.JK", "HGII.JK", 
           "HILL.JK", "HITS.JK", "HMSP.JK", "HOKI.JK", "HOMI.JK", "HOPE.JK", "HRME.JK", "HRTA.JK", 
           "HRUM.JK", "HUMI.JK", "HYGN.JK", "IATA.JK", "IBFN.JK", "IBOS.JK", "IBST.JK", "ICBP.JK", 
           "ICON.JK", "IDEA.JK", "IDPR.JK", "IFII.JK", "IFSH.JK", "IGAR.JK", "IKAI.JK", "IKAN.JK", 
           "IKBI.JK", "IKPM.JK", "IMAS.JK", "IMJS.JK", "IMPC.JK", "INAF.JK", "INAI.JK", "INCF.JK", 
           "INCI.JK", "INCO.JK", "INDF.JK", "INDO.JK", "INDR.JK", "INDS.JK", "INDX.JK", "INDY.JK", 
           "INET.JK", "INKP.JK", "INOV.JK", "INPC.JK", "INPP.JK", "INPS.JK", "INRU.JK", "INTA.JK", 
           "INTD.JK", "INTP.JK", "IOTF.JK", "IPAC.JK", "IPCC.JK", "IPCM.JK", "IPOL.JK", "IPPE.JK", 
           "IPTV.JK", "IRRA.JK", "IRSX.JK", "ISAP.JK", "ISAT.JK", "ISEA.JK", "ISSP.JK", "ITIC.JK", 
           "ITMA.JK", "ITMG.JK", "JARR.JK", "JAST.JK", "JATI.JK", "JAWA.JK", "JAYA.JK", "JECC.JK", 
           "JGLE.JK", "JIHD.JK", "JKON.JK", "JMAS.JK", "JPFA.JK", "JRPT.JK", "JSMR.JK", "JSPT.JK", 
           "JTPE.JK", "KAEF.JK", "KAQI.JK", "KARW.JK", "KBAG.JK", "KBLI.JK", "KBLM.JK", "KBLV.JK", 
           "KDSI.JK", "KDTN.JK", "KEEN.JK", "KEJU.JK", "KETR.JK", "KIAS.JK", "KICI.JK", "KIJA.JK", 
           "KING.JK", "KINO.JK", "KIOS.JK", "KJEN.JK", "KKES.JK", "KKGI.JK", "KLAS.JK", "KLBF.JK", 
           "KLIN.JK", "KMDS.JK", "KMTR.JK", "KOBX.JK", "KOCI.JK", "KOIN.JK", "KOKA.JK", "KONI.JK", 
           "KOPI.JK", "KOTA.JK", "KPIG.JK", "KRAS.JK", "KREN.JK", "KRYA.JK", "KSIX.JK", "KUAS.JK", 
           "LABA.JK", "LABS.JK", "LAJU.JK", "LAND.JK", "LAPD.JK", "LCKM.JK", "LEAD.JK", "LFLO.JK", 
           "LIFE.JK", "LINK.JK", "LION.JK", "LIVE.JK", "LMAX.JK", "LMPI.JK", "LMSH.JK", "LOPI.JK", 
           "LPCK.JK", "LPGI.JK", "LPIN.JK", "LPKR.JK", "LPLI.JK", "LPPF.JK", "LPPS.JK", "LRNA.JK", "LSIP.JK", "LTLS.JK", "LUCK.JK", "LUCY.JK", "MAHA.JK", "MAIN.JK", "MANG.JK", "MAPA.JK", "MAPB.JK", "MAPI.JK", "MARI.JK", "MARK.JK", "MASB.JK", "MAXI.JK", "MAYA.JK", "MBAP.JK", "MBMA.JK", "MBSS.JK", "MBTO.JK", "MCAS.JK", "MCOL.JK", "MCOR.JK", "MDIA.JK", "MDIY.JK", "MDKA.JK", "MDKI.JK", "MDLA.JK", "MDLN.JK", "MDRN.JK", "MEDC.JK", "MEDS.JK", "MEGA.JK", "MEJA.JK", "MENN.JK", "MERI.JK", "MERK.JK", "MFMI.JK", "MGLV.JK", "MGNA.JK", "MGRO.JK", "MHKI.JK", "MICE.JK", "MIDI.JK", "MIKA.JK", "MINA.JK", "MINE.JK", "MIRA.JK", "MITI.JK", "MKAP.JK", "MKNT.JK", "MKPI.JK", "MKTR.JK", "MLBI.JK", "MLIA.JK", "MLPL.JK", "MLPT.JK", "MMIX.JK", "MMLP.JK", "MNCN.JK", "MOLI.JK", "MORA.JK", "MPIX.JK", "MPMX.JK", "MPOW.JK", "MPPA.JK", "MPRO.JK", "MPXL.JK", "MRAT.JK", "MREI.JK", "MSIE.JK", "MSIN.JK", "MSJA.JK", "MSKY.JK", "MSTI.JK", "MTDL.JK", "MTEL.JK", "MTFN.JK", "MTLA.JK", "MTMH.JK", "MTPS.JK", "MTSM.JK", "MTWI.JK", "MUTU.JK", "MYOH.JK", "MYOR.JK", "MYTX.JK", "NAIK.JK", "NANO.JK", "NASA.JK", "NASI.JK", "NATO.JK", "NAYZ.JK", "NCKL.JK", "NELY.JK", "NEST.JK", "NETV.JK", "NFCX.JK", "NICE.JK", "NICK.JK", "NICL.JK", "NIKL.JK", "NINE.JK", "NIRO.JK", "NISP.JK", "NOBU.JK", "NPGF.JK", "NRCA.JK", "NSSS.JK", "NTBK.JK", "NZIA.JK", "OASA.JK", "OBAT.JK", "OBMD.JK", "OILS.JK", "OKAS.JK", "OLIV.JK", "OMED.JK", "OMRE.JK", "OPMS.JK", "PACK.JK", "PADA.JK", "PADI.JK", "PALM.JK", "PAMG.JK", "PANI.JK", "PANR.JK", "PANS.JK", "PART.JK", "PBID.JK", "PBRX.JK", "PBSA.JK", "PCAR.JK", "PDES.JK", "PDPP.JK", "PEGE.JK", "PEHA.JK", "PEVE.JK", "PGAS.JK", "PGEO.JK", "PGJO.JK", "PGLI.JK", "PGUN.JK", "PICO.JK", "PIPA.JK", "PJAA.JK", "PJHB.JK", "PKPK.JK", "PLAN.JK", "PLIN.JK", "PMJS.JK", "PMMP.JK", "PMUI.JK", "PNBN.JK", "PNBS.JK", "PNGO.JK", "PNIN.JK", "PNLF.JK", "PNSE.JK", "POLA.JK", "POLI.JK", "POLU.JK", "POLY.JK", "PORT.JK", "POWR.JK", "PPGL.JK", "PPRE.JK", "PPRI.JK", "PPRO.JK", "PRAY.JK", "PRDA.JK", "PRIM.JK", "PSAB.JK", "PSAT.JK", "PSDN.JK", "PSGO.JK", "PSKT.JK", "PSSI.JK", "PTBA.JK", "PTDU.JK", "PTIS.JK", "PTMP.JK", "PTMR.JK", "PTPP.JK", "PTPS.JK", "PTPW.JK", "PTRO.JK", "PTSN.JK", "PTSP.JK", "PUDP.JK", "PURA.JK", "PURI.JK", "PWON.JK", "PYFA.JK", "PZZA.JK", "RAAM.JK", "RAFI.JK", "RAJA.JK", "RALS.JK", "RANC.JK", "RATU.JK", "RBMS.JK", "RCCC.JK", "RDTX.JK", "REAL.JK", "RELF.JK", "RELI.JK", "RGAS.JK", "RICY.JK", "RIGS.JK", "RISE.JK", "RLCO.JK", "RMKE.JK", "RMKO.JK", "ROCK.JK", "RODA.JK", "RONY.JK", "ROTI.JK", "RSCH.JK", "RSGK.JK", "RUIS.JK", "RUNS.JK", "SAFE.JK", "SAGE.JK", "SAME.JK", "SAMF.JK", "SAPX.JK", "SATU.JK", "SBMA.JK", "SCCO.JK", "SCMA.JK", "SCNP.JK", "SDMU.JK", "SDPC.JK", "SDRA.JK", "SEMA.JK", "SFAN.JK", "SGER.JK", "SGRO.JK", "SHID.JK", "SHIP.JK", "SICO.JK", "SIDO.JK", "SILO.JK", "SIMP.JK", "SINI.JK", "SIPD.JK", "SKBM.JK", "SKLT.JK", "SKRN.JK", "SLIS.JK", "SMAR.JK", "SMBR.JK", "SMCB.JK", "SMDM.JK", "SMDR.JK", "SMGA.JK", "SMGR.JK", "SMIL.JK", "SMKL.JK", "SMKM.JK", "SMLE.JK", "SMMA.JK", "SMMT.JK", "SMRA.JK", "SMSM.JK", "SNLK.JK", "SOCI.JK", "SOFA.JK", "SOHO.JK", "SOLA.JK", "SONA.JK", "SOSS.JK", "SOTS.JK", "SOUL.JK", "SPMA.JK", "SPRE.JK", "SPTO.JK", "SQMI.JK", "SRAJ.JK", "SRSN.JK", "SRTG.JK", "SSIA.JK", "SSMS.JK", "SSTM.JK", "STAA.JK", "STAR.JK", "STRK.JK", "STTP.JK", "SULI.JK", "SUNI.JK", "SUPA.JK", "SUPR.JK", "SURE.JK", "SURI.JK", "SWAT.JK", "SWID.JK", "TALF.JK", "TAMA.JK", "TAMU.JK", "TAPG.JK", "TARA.JK", "TAXI.JK", "TAYS.JK", "TBIG.JK", "TBLA.JK", "TBMS.JK", "TCID.JK", "TCPI.JK", "TEBE.JK", "TELE.JK", "TFAS.JK", "TFCO.JK", "TGKA.JK", "TGRA.JK", "TGUK.JK", "TIFA.JK", "TINS.JK", "TIRA.JK", "TIRT.JK", "TKIM.JK", "TLDN.JK", "TLKM.JK", "TMAS.JK", "TMPO.JK", "TNCA.JK", "TOBA.JK", "TOOL.JK", "TOPS.JK", "TOSK.JK", "TOTL.JK", "TOTO.JK", "TOWR.JK", "TPIA.JK", "TPMA.JK", "TRGU.JK", "TRIM.JK", "TRIN.JK", "TRIS.JK", "TRJA.JK", "TRON.JK", "TRST.JK", "TRUE.JK", "TRUK.JK", "TRUS.JK", "TSPC.JK", "TUGU.JK", "TYRE.JK", "UANG.JK", "UCID.JK", "UDNG.JK", "UFOE.JK", "ULTJ.JK", "UNIC.JK", "UNIQ.JK", "UNSP.JK", "UNTD.JK", "UNTR.JK", "UNVR.JK", "URBN.JK", "UVCR.JK", "VAST.JK", "VERN.JK", "VICI.JK", "VICO.JK", "VINS.JK", "VISI.JK", "VIVA.JK", "VKTR.JK", "VOKS.JK", "VRNA.JK", "VTNY.JK", "WAPO.JK", "WEGE.JK", "WEHA.JK", "WGSH.JK", "WICO.JK", "WIDI.JK", "WIFI.JK", "WIIM.JK", "WIKA.JK", "WINE.JK", "WINR.JK", "WINS.JK", "WIRG.JK", "WMUU.JK", "WOMF.JK", "WOOD.JK", "WOWS.JK", "WSBP.JK", "WTON.JK", "XCIS.JK", "YELO.JK", "YOII.JK", "YPAS.JK", "YULE.JK", "YUPI.JK", "ZATA.JK", "ZBRA.JK", "ZINC.JK", "ZONE.JK", "ZYRX.JK"
           ]

# Data Download
CACHE_DIR = Path(__file__).parent / "cache_yfinance"
CACHE_MAX_AGE_HOURS = 8
BATCH_SIZE = 60
DOWNLOAD_PERIOD = "1y"
DOWNLOAD_INTERVAL = "1d"

# Ichimoku
ICHIMOKU_TENKAN = 9
ICHIMOKU_KIJUN = 26
ICHIMOKU_SENKOU_B = 52

# Donchian
DONCHIAN_PERIOD = 20

# SuperTrend - Multi Instance (Layered Entry)
# Fast: sensitif untuk entry awal
ST_FAST_PERIOD = 7
ST_FAST_MULTIPLIER = 2.0

# Medium: konfirmasi (default lama)
ST_MED_PERIOD = 10
ST_MED_MULTIPLIER = 3.5

# Slow: filter trend utama (gate)
ST_SLOW_PERIOD = 14
ST_SLOW_MULTIPLIER = 4.0

# Backward compatibility - default pakai medium
ATR_LENGTH = ST_MED_PERIOD
ATR_MULTIPLIER = ST_MED_MULTIPLIER

# ADX
ADX_LENGTH = 14
ADX_THRESHOLD = 25

# AVWAP
AVWAP_LOOKBACK = 5

# Volume
VOLUME_MA_PERIOD = 20

# Volume Quality
MIN_DOLLAR_VOLUME = 500_000_000  # Rp 500 juta/hari minimum
VOL_PER_ATR_MIN = 100_000  # Minimum dollar volume per ATR point
MAX_VOL_CV = 1.5  # Maximum coefficient of variation for volume stability

# Volume Pressure
OBV_MA_PERIOD = 20
DELTA_MA_PERIOD = 20

# Momentum Oscillators
RSI_PERIOD = 14
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70

MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

STOCH_K = 14
STOCH_D = 3
STOCH_SMOOTH = 3
STOCH_OVERSOLD = 20

# Elliott Wave
ELLIOTT_SWING_LOOKBACK = 5
FIBONACCI_LEVELS = [0.382, 0.5, 0.618, 0.786]

# Entry Zone
ENTRY_ZONE_MAX_ATR = 0.75
ENTRY_ZONE_MIN_ATR = 0.25
ENTRY_ZONE_MAX_PCT = 0.04

# Risk Management
ATR_PERIOD_RM = 14
SL_MULTIPLIER = 1.5
RR1 = 1.5
RR2 = 2.5
RR3 = 3.0
SELECTED_TP = "TP1"

# Partial Exit (% shares dijual di setiap TP)
TP1_PCT = 60
TP2_PCT = 25
TP3_PCT = 15

# Market Regime
JKSE_TICKER = "^JKSE"

# Volatility Contraction
ATR_CONTRACTION_SHORT = 10
ATR_CONTRACTION_LONG = 50
VOL_CONTRACTION_THRESHOLD = 0.8

# Near Resistance
RESISTANCE_ATR_MULTIPLIER = 1.5

# Volume Setup
VOL_MA_SHORT = 5
VOLUME_RISING_LOOKBACK = 3

# Fresh Signal
FRESH_SIGNAL_BARS = 3

# Too Late Filter - Extension & Distribution Detection
MAX_RUNUP = 0.30           # Max 30% run-up dari low 50 hari
MAX_RUNUP_BLOCK = 0.50     # Block entry jika run-up > 50%
MAX_PRICE_TO_MA20 = 0.15   # Max 15% di atas MA20
MAX_PRICE_TO_AVWAP = 0.10  # Max 10% di atas AVWAP
STOCH_OVERBOUGHT = 80      # Stochastic overbought threshold

# Monte Carlo
MC_N_SIM = 1000
MC_HORIZON = 20

# Performance / Position Sizing
INITIAL_CAPITAL = 100_000_000     # Rp 100 juta
RISK_PER_TRADE_PCT = 2.0          # 2% risk per trade
POSITION_SIZE = 10_000_000        # Rp 10 juta per entry
MAX_POSITIONS = 12                # Max concurrent positions
BENCHMARK_TICKER = "^JKSE"

# Display
MAX_DISPLAY = 20

# Setup types
SETUP_ORDER = [
    "PRE_BREAKOUT", "VCP", "TIGHT_BASE_BREAKOUT", "BASE_ON_BASE",
    "BULL_FLAG", "BREAKOUT", "PULLBACK_MA20", "ACCUMULATION", "EARLY_REVERSAL"
]

SIGNAL_MAP = {
    "PRE_BREAKOUT": "BUY",
    "VCP": "BUY",
    "TIGHT_BASE_BREAKOUT": "STRONG BUY",
    "BASE_ON_BASE": "BUY",
    "BULL_FLAG": "BUY",
    "BREAKOUT": "STRONG BUY",
    "PULLBACK_MA20": "BUY",
    "ACCUMULATION": "BUY",
    "EARLY_REVERSAL": "BUY",
}

COLOR_MAP = {
    "PRE_BREAKOUT": "#FFA726",
    "VCP": "#AB47BC",
    "TIGHT_BASE_BREAKOUT": "#26A69A",
    "BASE_ON_BASE": "#5C6BC0",
    "BULL_FLAG": "#FF7043",
    "BREAKOUT": "#66BB6A",
    "PULLBACK_MA20": "#FFCA28",
    "ACCUMULATION": "#42A5F5",
    "EARLY_REVERSAL": "#EF5350",
    "NONE": "#888",
}
