#include <windows.h>
#include <stdio.h>

void envoyer_touche(WORD vk_code, BOOL appui) {
    INPUT input = {0};
    input.type = INPUT_KEYBOARD;
    input.ki.wVk = vk_code;
    if (!appui) {
        input.ki.dwFlags = KEYEVENTF_KEYUP;
    }
    SendInput(1, &input, sizeof(INPUT));
}

int main(void) {
    Sleep(2000); // laisse le temps de cliquer dans la fenetre cible

    envoyer_touche('A', TRUE);   // touche enfoncee
    envoyer_touche('A', FALSE);  // touche relachee

    return 0;
}