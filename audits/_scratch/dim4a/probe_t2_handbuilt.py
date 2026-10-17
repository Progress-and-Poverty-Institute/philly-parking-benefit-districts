"""Known-answer tests of B2 (no-curb classes), B3 (frontage share), B4/B5 (priced curb, zone box)."""
import numpy as np, pandas as pd, geopandas as gpd
from shapely.geometry import LineString, box, Point
from phillyparking._config import load_config
from phillyparking.spatial.join import join_zoning
from phillyparking.spatial.segments import build_segments, assign_priced_curb
from phillyparking.spatial.zones import zone_for_point

X0,Y0=486_000.0,4_422_000.0
C="Commercial/Commercial Mixed-Use"; R="Residential/Multi-Family/Residential Mixed-Use"; I="Industrial"
def utm(geoms,**cols): return gpd.GeoDataFrame(dict(cols),geometry=list(geoms),crs=32618)
def hl(x,y,L=80.0): return LineString([(x,y),(x+L,y)])
out=[]
def chk(name,got,want,tol=1e-6):
    ok = abs(got-want)<=tol if isinstance(want,(int,float)) else got==want
    print(("PASS " if ok else "FAIL ")+name, "got",got,"want",want); out.append(ok)

# ---- B2: classes
cfg=load_config("zones")["priced_curb"]; print("cfg",cfg)
classes=[0,1,2,3,4,5,6,9,10,12,13,14,15,18,np.nan,"7"]
streets=utm([hl(X0,Y0+50*i) for i in range(len(classes))],seg_id=list(range(len(classes))),**{"class":classes}).to_crs(4326)
seg=build_segments(streets=streets)
kept=sorted(seg.street_class.dropna().unique().tolist()); print("kept classes",kept, "NaN class rows",int(seg.street_class.isna().sum()))
chk("kept classes = 0,2,3,4,5,7,13,18 (+NaN row)",kept,[0,2,3,4,5,7,13,18])
chk("no_curb_dropped",seg.attrs["build_report"]["no_curb_dropped"],7)
# classes that gate pricing
seg["commercial_frontage_share"]=1.0; seg["zone_id"]="ccc"
p=assign_priced_curb(seg,inventory=False)
chk("priced classes only 2-5",sorted(p.loc[p.priced_curb,"street_class"].unique().tolist()),[2,3,4,5])
print("NaN-class row priced?",bool(p.loc[p.street_class.isna(),"priced_curb"].any()))

# ---- B3: frontage share. segment along x from X0..X0+80 at y=Y0; buffer flat 25 m => x in [X0,X0+80], y in [Y0-25,Y0+25]
seg1=utm([hl(X0,Y0)],segment_id=["s"]).to_crs(4326)
def share(parts,buffer_m=25):
    z=utm([g for g,_ in parts],zoninggroup=[k for _,k in parts]).to_crs(4326)
    return join_zoning(seg1,z,buffer_m=buffer_m)["commercial_frontage_share"].iloc[0]
# lots 10-50 m from centerline on both sides, commercial north, residential south => 0.5
chk("N comm / S res (10m offset) = 0.5", share([(box(X0-50,Y0+10,X0+130,Y0+50),C),(box(X0-50,Y0-50,X0+130,Y0-10),R)]),0.5)
# unequal areas inside the buffer: north lot reaches y+25 (15 m deep within buffer), south lot 10..25 as well => equal: change south to start 20 m (5 m deep)
chk("N 15m deep comm, S 5m deep res = 0.75", share([(box(X0-50,Y0+10,X0+130,Y0+50),C),(box(X0-50,Y0-50,X0+130,Y0-20),R)]),0.75)
# lot beyond the buffer => 0 (no zoned land in reach)
chk("lots 30 m away => 0", share([(box(X0-50,Y0+30,X0+130,Y0+60),C)]),0.0)
# flat ends: a commercial lot beyond the end of the segment but within 25 m of the endpoint must NOT count
chk("lot past the segment end (flat cap) => 0", share([(box(X0+81,Y0-25,X0+120,Y0+25),C)]),0.0)
# lot overlapping the segment end by 1 m counts only the part within [X0,X0+80]
chk("end-overlap area counted only inside flat buffer, residential rest => ", share([(box(X0+79,Y0+10,X0+120,Y0+25),C),(box(X0-50,Y0-25,X0+78,Y0-10),R)]), (1*15)/(1*15+78*15+0), 1e-6)  # computed below
# zoning that contains the centerline (zoning laid over the street): R lot over the whole buffer
chk("zoning covering the street itself", share([(box(X0-50,Y0-50,X0+130,Y0+50),R)]),0.0)
# tiny commercial sliver, the rest of the buffer unzoned => share 1.0 (ratio of zoned land only)
sl=share([(box(X0+10,Y0+10,X0+11,Y0+11),C)]); print("1 m2 commercial sliver, rest unzoned => share",sl); 
# overlapping polygons double count?
ov=share([(box(X0-50,Y0+10,X0+130,Y0+50),C),(box(X0-50,Y0+10,X0+130,Y0+50),R)]); print("identical overlapping C and R polygons => share",ov,"(0.5 = double counted area)")
# industrial/other group counts as zoned-not-commercial
chk("industrial lot only => 0", share([(box(X0-50,Y0+10,X0+130,Y0+50),I)]),0.0)
# diagonal line: flat caps
sd=utm([LineString([(X0,Y0),(X0+57,Y0+57)])],segment_id=["d"]).to_crs(4326)
z=utm([box(X0-100,Y0-100,X0+200,Y0+200)],zoninggroup=[C]).to_crs(4326)
chk("diagonal inside all-commercial => 1",join_zoning(sd,z)["commercial_frontage_share"].iloc[0],1.0)

# ---- B5: zone_for_point, smallest box
zones=load_config("zones")["zones"]
for z in zones: print(z["id"],"area",(z["bbox"]["east"]-z["bbox"]["west"])*(z["bbox"]["north"]-z["bbox"]["south"]))
chk("ccc point (Rittenhouse-ish -75.16,39.95)",zone_for_point(-75.16,39.95,zones),"ccc")
chk("point in cca only (-75.185,39.97)",zone_for_point(-75.185,39.97,zones),"cca")
chk("point in cca & ucity (-75.185,39.955) -> ucity (smaller)",zone_for_point(-75.185,39.955,zones),"ucity")
chk("point in cca & fishtown (-75.135,39.97) -> fishtown",zone_for_point(-75.135,39.97,zones),"fishtown")
chk("point in cca & south_philly shared edge lat 39.935 -> south_philly (smaller)",zone_for_point(-75.16,39.935,zones),"south_philly")
chk("outside (-75.30,40.0) -> other",zone_for_point(-75.30,40.0,zones),"other")
# pairwise box overlaps
import itertools
for a,b in itertools.combinations(zones,2):
    A,B=a["bbox"],b["bbox"]
    w=min(A["east"],B["east"])-max(A["west"],B["west"]); h=min(A["north"],B["north"])-max(A["south"],B["south"])
    if w>=0 and h>=0: print("overlap",a["id"],b["id"],"w",round(w,4),"h",round(h,4),"area",w*h)
# ---- assign_priced_curb: zone_id only for priced curb
f=pd.DataFrame({"segment_id":list("abcd"),"has_meter":False,"street_class":[5,5,13,3],"commercial_frontage_share":[0.5,0.4999,1.0,1.0],"zone_id":["ccc","ccc","ccc","other"]})
q=assign_priced_curb(f,inventory=False)
chk("threshold >= 0.5 inclusive, 0.4999 excluded, class 13 excluded, other-box excluded",q.priced_curb.tolist(),[True,False,False,False])
chk("zone_id = box only if priced",q.zone_id.tolist(),["ccc","other","other","other"])
chk("zone_box preserved",q.zone_box.tolist(),["ccc","ccc","ccc","other"])
# float equality at 0.5: share computed as comm/zoned may land at 0.4999999
print("ALL PASS" if all(out) else f"{out.count(False)} FAIL")
