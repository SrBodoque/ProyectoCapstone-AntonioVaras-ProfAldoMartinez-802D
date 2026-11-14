"""LimpIA: entrada unica para video, camara y calibracion de zonas."""
if __name__=='__main__':
    from multiprocessing import freeze_support
    freeze_support()
    from src.launcher import main
    raise SystemExit(main())
