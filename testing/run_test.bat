@echo off
echo ========================================
echo    MENDO ALGORITHM TESTING SUITE
echo ========================================
echo.
echo Running comprehensive tests...
echo.

cd /d "%~dp0.."
python testing\test_algorithm.py

echo.
echo ========================================
echo Tests complete! 
echo.
echo View results:
echo   1. Open testing\view_results.html in browser
echo   2. Check testing\benchmark\results\ folder
echo ========================================
echo.
pause
