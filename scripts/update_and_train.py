import json
from app.db import init_db
from app.services.market_data import update_all
from app.services.features import build_dataset
from app.models.ensemble import train
from app.services.scoring import generate_prediction

def main():
    init_db()
    status=update_all("3y")
    ds=build_dataset()
    bundle=train(ds)
    pred=generate_prediction(ds)
    print(json.dumps({"status":status,"metrics":bundle.metrics,"prediction":pred},ensure_ascii=False,indent=2,default=str))
if __name__=="__main__": main()
