// Parametric 35 x 20 mm POC medicine carrier and magazine tube
// Change `part` to export a specific component.
part = "container_body";
// Options: container_body, lid_normal, lid_loose, lid_tight,
// dummy_container, tube_180, tube_90, tube_cap, dummy_blister

$fn = 64;
container_l = 35.0;
container_w = 20.0;
container_h = 15.0;
body_h = 13.8;
wall = 1.2;
bottom = 1.2;
outer_r = 2.0;
lid_top_t = 1.2;
lid_plug_d = 1.4;
lid_top_l = 34.6;
lid_top_w = 19.6;

tube_in_l = 36.2;
tube_in_w = 21.2;
tube_in_r = 2.4;
tube_wall = 2.4;
tube_out_l = 41.0;
tube_out_w = 26.0;
tube_out_r = 4.8;
flange_l = 58.0;
flange_w = 42.0;
flange_t = 4.0;
flange_hole_d = 4.5;
flange_hole_dx = 46.0;
flange_hole_dy = 30.0;

module rr2d(l,w,r) {
    offset(r=r) square([l-2*r,w-2*r], center=true);
}

module container_body() {
    difference() {
        linear_extrude(body_h) rr2d(container_l,container_w,outer_r);
        translate([0,0,bottom])
            linear_extrude(body_h-bottom+0.2)
                rr2d(container_l-2*wall,container_w-2*wall,max(0.6,outer_r-wall));
    }
}

module lid(clearance=0.30) {
    cavity_l = container_l - 2*wall;
    cavity_w = container_w - 2*wall;
    union() {
        linear_extrude(lid_plug_d)
            rr2d(cavity_l-2*clearance,cavity_w-2*clearance,max(0.5,outer_r-wall-clearance));
        translate([0,0,lid_plug_d])
            linear_extrude(lid_top_t)
                rr2d(lid_top_l,lid_top_w,outer_r-0.2);
    }
}

module dummy_container() {
    linear_extrude(container_h) rr2d(container_l,container_w,outer_r);
}

module magazine_tube(h=180) {
    difference() {
        union() {
            linear_extrude(flange_t) rr2d(flange_l,flange_w,5);
            translate([0,0,flange_t])
                linear_extrude(h)
                    difference() {
                        rr2d(tube_out_l,tube_out_w,tube_out_r);
                        rr2d(tube_in_l,tube_in_w,tube_in_r);
                    }
        }
        translate([0,0,-0.1])
            linear_extrude(h+flange_t+0.2)
                rr2d(tube_in_l,tube_in_w,tube_in_r);
        for (x=[-flange_hole_dx/2,flange_hole_dx/2])
            for (y=[-flange_hole_dy/2,flange_hole_dy/2])
                translate([x,y,-0.1]) cylinder(d=flange_hole_d,h=flange_t+0.2);
    }
}

module tube_cap() {
    union() {
        linear_extrude(3.0)
            rr2d(tube_in_l-0.4,tube_in_w-0.4,2.1999999999999997);
        translate([0,0,3.0])
            linear_extrude(2.0) rr2d(42.0,27.0,4);
    }
}

module dummy_blister() {
    linear_extrude(8.0)
        rr2d(30.0,15.0,3.5);
}

if (part == "container_body") container_body();
else if (part == "lid_normal") lid(0.30);
else if (part == "lid_loose") lid(0.40);
else if (part == "lid_tight") lid(0.20);
else if (part == "dummy_container") dummy_container();
else if (part == "tube_180") magazine_tube(180);
else if (part == "tube_90") magazine_tube(90);
else if (part == "tube_cap") tube_cap();
else if (part == "dummy_blister") dummy_blister();
