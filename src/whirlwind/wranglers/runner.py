"""whirlwind.wranglers.runner 

    PURPOSE:
        - contains runners for wrangling commands 

    BEHAVIOR:
        - instantiate runner which wraps all wrangling behaviors. 
        - WrangleMosaicsRunner:
            - instantiate Down sampling params (DSParams) from config and user input 
            - use click to dispatch gdal_translate function 


"""


class WrangleMosaicsRunner: 
    DSParams: 
