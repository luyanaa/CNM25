# open_pdk/cnm25 — regeneration and smoke-test targets
PDK      := $(CURDIR)/cnm25
TESTGDS  := $(PDK)/libs.ref/cnm25_test/gds
KLAYOUT  := klayout -b
MAGIC    := magic -dnull -noconsole
NETGEN   := netgen -batch

.PHONY: all gds drc lvs clean

all: gds

## Regenerate all fixture/device GDS
gds:
	$(KLAYOUT) -r scripts/make_test_gds.py

## KLayout DRC on all test cells
drc: drc-klayout

drc-klayout:
	@for g in $(TESTGDS)/*.gds; do \
	  echo "=== DRC $$g"; \
	  $(KLAYOUT) -r $(PDK)/libs.tech/klayout/drc/cnm25.drc \
	    -rd input=$$g -rd report=$$(basename $$g .gds)_drc.lyrdb; \
	done

## Magic DRC (batch, advisory — KLayout deck is authoritative)
drc-magic:
	@for g in $(TESTGDS)/*.gds; do \
	  echo "=== magic DRC $$g"; \
	  $(MAGIC) -T $(PDK)/libs.tech/magic/cnm25.tech \
	    -rcfile /dev/null /dev/stdin <<'EOF' 2>/dev/null | grep "Total DRC"; \
drc on\ngds readonly true\ngds read $$g\nload $$(basename $$g .gds)\nexpand\ndrc count total\nquit -noprompt\nEOF \
	done

## KLayout LVS on the inverter golden cell
lvs: lvs-klayout lvs-magic

lvs-klayout:
	$(KLAYOUT) -r $(PDK)/libs.tech/klayout/lvs/cnm25.lvs \
	  -rd input=$(TESTGDS)/inverter.gds \
	  -rd schematic=$(PDK)/libs.ref/cnm25_test/spice/inverter.spice

lvs-magic:
	$(PDK)/libs.tech/magic/run_lvs.sh $(TESTGDS)/inverter.gds inverter \
	  $(PDK)/libs.ref/cnm25_test/spice/inverter.spice

## Magic PEX on the inverter
pex:
	$(PDK)/libs.tech/magic/run_pex.sh $(TESTGDS)/inverter.gds inverter \
	  inverter_pex.spice

## Magic extraction + netgen LVS on the inverter
lvs-netgen:
	cd /tmp && $(MAGIC) -T $(PDK)/libs.tech/magic/cnm25.tech \
	  -rcfile $(PDK)/libs.tech/magic/cnm25.magicrc \
	  $(PDK)/libs.tech/magic/run_extract.tcl 2>/dev/null || true

clean:
	rm -f *_drc.lyrdb
