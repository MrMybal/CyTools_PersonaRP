// Windows launcher: opens the Dear ImGui window directly, with no console window.
#define UNICODE
#define _UNICODE
#include <windows.h>
#include <string>

int WINAPI wWinMain(HINSTANCE, HINSTANCE, PWSTR arguments, int) {
    wchar_t path[32768];
    GetModuleFileNameW(nullptr, path, 32768);
    std::wstring root(path);
    root.resize(root.find_last_of(L"\\/"));
    std::wstring python = root + L"\\runtime\\python\\Scripts\\pythonw.exe";
    std::wstring command = L"\"" + python + L"\" \"" + root + L"\\runtime\\bootstrap.py\" " + arguments;
    STARTUPINFOW startup{};
    startup.cb = sizeof(startup);
    PROCESS_INFORMATION process{};
    if (!CreateProcessW(python.c_str(), command.data(), nullptr, nullptr, FALSE, 0,
                        nullptr, root.c_str(), &startup, &process)) {
        MessageBoxW(nullptr,
                    L"Runtime missing, or the application could not start. See LISEZ-MOI.md.",
                    L"CyTools_PersonaRP", MB_ICONERROR);
        return 1;
    }
    CloseHandle(process.hThread);
    CloseHandle(process.hProcess);
    return 0;
}
