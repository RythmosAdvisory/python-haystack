/*
    Basic types tests.
*/
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

struct a {
    unsigned char a;
    unsigned short b;
    unsigned int c;
    unsigned long d;
    unsigned long long e;
    float f;
    double g;
    long double h;
};

union au {
    unsigned char a;
    unsigned short b;
    unsigned int c;
    unsigned long d;
    unsigned long long e;
    float f;
    double g;
    long double h;
};

int test1(){
    {
        struct a * ptr;

        ptr = (struct a *) malloc(sizeof(struct a));
        ptr->a = 'a';
        ptr->b = 98;
        ptr->c = 0x63;
        ptr->d = 0x640ff046;
        ptr->e = 0x6545454545454565;
        ptr->f = 10.0;
        ptr->g = 10.0e-5;
        ptr->h = 10.0e-300;

        printf("s: struct_a\n");

        printf("v: a %d\nv: b %d\nv: c %d\nv: d %ld\nv: e %lld\n",ptr->a,ptr->b,
                                ptr->c, ptr->d, ptr->e);
        printf("v: f %lf\n",ptr->f);
        printf("v: g %lf\n",ptr->g);
        printf("v: h %LG\n",ptr->h);

        printf("o: struct_a 0x%lx\n",(unsigned long )ptr);
        printf("t: sizeof %ld\n\n",sizeof(struct a));
    }    
    {
        union au * ptr;

        ptr = (union au *) malloc(sizeof(union au));
        ptr->e = 0x6545454545454565;

        printf("s: union_au\n");

        printf("v: d %ld\n",ptr->d);
        printf("v: g %lf\n",ptr->g);
        printf("v: h %LG\n",ptr->h);

        printf("o: union_au 0x%lx\n",(unsigned long )ptr);
        printf("t: sizeof %ld\n\n",sizeof(union au));
    }    
    return 0;
}

union b {
    signed char a;
    signed short b;
    signed int c;
    signed long d;
    signed long long e;
    float f;
    double g;
    long double h;
};

int test2(){
    {
        union b * ptr;

        ptr = (union b *) malloc(sizeof(union b));
        ptr->h = 10.0e-300;
        ptr->a = 'a';
        ptr->b = -98;
        ptr->c = +99;
        //printf("v: a %d\nv: b %d\nv: c %d\nv: d %ld\nv: e %lld\n",ptr->a,ptr->b,
        //                        ptr->c, ptr->d, ptr->e);
        //printf("v: g %lf\n",ptr->g);
        //printf("v: h %LG\nfix\n",ptr->h);
        ptr->e = -5;

        printf("s: union_b\n");

        printf("v: a %d\nv: b %d\v: nc %d\nv: d %ld\nv: e %lld\n",ptr->a,ptr->b,
                                ptr->c, ptr->d, ptr->e);


        printf("o: union_b 0x%lx\n",(unsigned long )ptr);
        printf("t: sizeof %ld\n\n",sizeof(union b));
    }    
    return 0;
}


struct c {
    unsigned int a1;
    unsigned int b1:4;
    unsigned int c1:10;
    unsigned int d1:2;
    signed char a2;
    unsigned int b2:4;
    unsigned int c2:10;
    unsigned long long d2:3;
    int h;
};

int test3(){
    {
        struct c * ptr;

        ptr = (struct c *) malloc(sizeof(struct c));
        ptr->a1 = 0xaaaaaaaa;
        ptr->b1 = 3;
        ptr->c1 = 8;
        ptr->d1 = 1;
        ptr->a2 = 'A';
        ptr->b2 = 3;
        ptr->c2 = 8;
        ptr->d2 = 1;

        printf("s: struct_c\n");

        printf("v: a1 %d\nv: b1 %d\nv: c1 %d\nv: d1 %d\n",ptr->a1, ptr->b1,
                                ptr->c1, ptr->d1);
        printf("v: a2 %d\nv: b2 %d\nv: c2 %d\nv: d2 %d\n",ptr->a2, ptr->b2,
                                ptr->c2, ptr->d2);

        printf("o: struct_c 0x%lx\n",(unsigned long )ptr);
        printf("t: sizeof %ld\n\n",sizeof(struct c));
    }    
    return 0;
}

struct d {
    void * a;
    struct a * b;
    union au * b2;
    struct a c[10];
    union au c2[10];
    union au * c3[10];
    struct d * d;
    int * e;
    int f[10];
    int * f2[10];
    char g;
    char * h;
    char i[32];
    char * j[40];
};

int test4(){
    {
        int i = 0;
        int * pi, *pi2 = 0;
        char * txt, *txt2 = 0;
        struct a * ptra;
        union au * ptrau;
        struct d * ptr;

        ptra = (struct a *) malloc(sizeof(struct a));
        ptra->e = 41;
        ptrau = (union au *) malloc(sizeof(union au));
        ptrau->e = 42;
        pi = (int *) malloc(sizeof(int));
        (*pi) = 101;
        pi2 = (int *) malloc(sizeof(int));
        (*pi2) = 102;
        txt = (char *) malloc(42);
        strcpy(txt,"lorem ipsum\0");
        txt2 = (char *) malloc(42);
        strcpy(txt2,"lorem ipsum 2\0");
        
        ptr = (struct d *) malloc(sizeof(struct d));
        ptr->a = (void *) 0xaaaaaaaa;
        ptr->b = ptra;
        ptr->b2 = ptrau;
        for ( i=0;i<10;i++) {
            ptr->c[i].a = i;
            ptr->c[i].e = 40;
            ptr->c2[i].e = 39;
            ptr->f[i] = 66;
            ptr->f2[i] = pi;
            ptr->c3[i] = ptrau;
        }
        ptr->d = ptr;
        ptr->e = pi;
        ptr->f2[9] = pi2;
        ptr->g = 'g';
        ptr->h = txt;
        strcpy(ptr->i, txt2);
        for ( i=0;i<40;i+=2)
            ptr->j[i] = txt;
            ptr->j[i+1] = txt2;

        //printf("v: sizeof struct d %ld\n", sizeof(struct d));
        printf("s: struct_d\n");

        printf("o: struct_d 0x%lx\n",(unsigned long )ptr);
        printf("t: sizeof %ld\n\n",sizeof(struct d));
    }    
    return 0;
}

int main(){


    test1();
    test2();
    test3();
    test4();

    printf("pid %d\n",getpid());
    fflush(stdout);
    sleep(-1);

    return 0;
}


