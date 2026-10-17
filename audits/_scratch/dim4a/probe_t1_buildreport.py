# Shows where attrs["build_report"] is lost between build_segments and the saved meta.
import geopandas as gpd, logging
from phillyparking.io import opendataphilly, census
from phillyparking.spatial.segments import build_segments
from phillyparking.spatial.join import join_acs
streets=opendataphilly.fetch_streets(); rpp=opendataphilly.fetch_rpp_zones(); nb=opendataphilly.fetch_neighborhoods()
seg=build_segments(streets=streets,rpp_zones=rpp,neighborhoods=nb)
print("after build_segments attrs keys:",list(seg.attrs))
acs=census.fetch_acs_block_groups()
seg2=join_acs(seg,acs,uncovered="drop")
print("after join_acs attrs keys:",list(seg2.attrs),"rows",len(seg),"->",len(seg2))
