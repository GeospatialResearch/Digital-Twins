from src import run
from src.digitaltwin import get_data_from_db
from src.lidar import lidar_metadata_in_db, bg_flood_model

if __name__ == '__main__':
    print("run.main()")
    run.main()
    print("get_data_from_db.main()")
    get_data_from_db.main()
    print("lidar_metadata_in_db.main()")
    lidar_metadata_in_db.main()
    print("bg_flood_model.main()")
    bg_flood_model.main()
