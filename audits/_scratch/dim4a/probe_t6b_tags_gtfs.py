import pandas as pd
from phillyparking.io import osm_loader, gtfs_loader
a=osm_loader.load_pois()
b=osm_loader.load_pois(tags={"amenity":["school"]})
print("load_pois default rows",len(a),"; load_pois(tags={'amenity':['school']}) rows",len(b),"identical frame:",a.equals(b))
print(" marker source of the second call:",b.attrs["provenance"]["source"])
print(" tag columns present:",[c for c in ("amenity","shop","office") if c in a.columns],"; amenity values top:",a["amenity"].value_counts().head(6).to_dict())
feeds=gtfs_loader.load_septa_feeds()
for n,f in feeds.items():
    d=gtfs_loader._service_date(f); print("feed",n,"service date used",d,"dow",pd.Timestamp(d).day_name(),"feed dates",f.get_dates()[0],"..",f.get_dates()[-1],"; n active trips that date",len(f.get_trips(d)))
sf=gtfs_loader.load_stop_frequency()
print("stops",len(sf),"trips_per_hour quantiles",sf.trips_per_hour.quantile([0,.5,.9,.99,1]).round(2).to_dict(), "service dates", sf.service_date.unique().tolist())
