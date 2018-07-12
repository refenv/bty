package bzi

import (
	"github.com/safl/bty/conf"
	"github.com/safl/bty/finf"
)

type Bzi struct {
	Finf	finf.Finf	`json:"finf"`
}

// Load Operating System Disk Images
func Load(cfg conf.Conf, bzis *[]Bzi, flags int) {

	for _, finf := range finf.FinfLoad(
		cfg.Locs.Bzis,
		cfg.Patterns.BziExt,
		finf.FINF_CHECKSUM,
	) {
		*bzis = append(*bzis, Bzi{
			Finf: finf,
		})
	}

}

