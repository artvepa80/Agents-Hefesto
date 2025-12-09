function veryComplexFunction(x: number, y: number): number {
    if (x > 10) {
        for (let i = 0; i < x; i++) {
            if (i % 2 === 0) {
                while (i < y) {
                    if (i % 3 === 0) {
                        switch (i) {
                            case 1: return i;
                            case 2: return i * 2;
                            default: i++;
                        }
                    }
                    i++;
                }
            }
        }
    }
    return x + y;
}
